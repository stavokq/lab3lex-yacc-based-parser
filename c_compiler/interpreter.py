from __future__ import annotations
from dataclasses import dataclass
import math
from typing import Any

from .ast_nodes import (
    ASTNode,
    ArrayAccess,
    ArrayInitializer,
    Assignment,
    BinaryOp,
    Block,
    BreakStmt,
    ContinueStmt,
    DoWhileStmt,
    EmptyStmt,
    ExprStmt,
    ForStmt,
    FuncCall,
    FunctionDecl,
    Identifier,
    IfStmt,
    Literal,
    Program,
    ReturnStmt,
    UnaryOp,
    VarDecl,
    WhileStmt,
)


class _ReturnSignal(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


class _BreakSignal(Exception):
    pass


class _ContinueSignal(Exception):
    pass


class RuntimeLimitError(Exception):
    pass


@dataclass
class ExecutionResult:
    stdout: str
    return_value: Any
    variables: dict[str, Any]
    steps: int
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stdout": self.stdout,
            "returnValue": self.return_value,
            "variables": {k: _serialize_val(v) for k, v in self.variables.items()},
            "steps": self.steps,
            "error": self.error,
        }


def _serialize_val(v: Any) -> Any:
    if isinstance(v, (int, float, str, bool)) or v is None:
        return v
    if isinstance(v, list):
        return [_serialize_val(x) for x in v]
    return str(v)


def _cast_c_type(value: Any, c_type: str) -> Any:
    base = c_type.replace("[]", "")
    if isinstance(value, list):
        return [_cast_c_type(x, base) for x in value]
    if base == "int":
        if isinstance(value, str) and len(value) == 1:
            return ord(value)
        return int(value)
    if base in ("float", "double"):
        return float(value)
    if base == "bool":
        return bool(value)
    if base == "char":
        if isinstance(value, int):
            return chr(value & 0xFF)
        if isinstance(value, str) and value:
            return value[0]
        return "\0"
    return value


def _default_value(c_type: str) -> Any:
    if c_type in ("float", "double"):
        return 0.0
    if c_type == "bool":
        return False
    if c_type == "char":
        return "\0"
    return 0


class Environment:
    def __init__(self, parent: Environment | None = None) -> None:
        self.parent = parent
        self.values: dict[str, Any] = {}
        self.types: dict[str, str] = {}

    def define(self, name: str, value: Any, c_type: str) -> None:
        self.values[name] = _cast_c_type(value, c_type)
        self.types[name] = c_type

    def get(self, name: str) -> Any:
        if name in self.values:
            return self.values[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise NameError(f"Змінна '{name}' не знайдена під час виконання")

    def get_type(self, name: str) -> str:
        if name in self.types:
            return self.types[name]
        if self.parent is not None:
            return self.parent.get_type(name)
        return "int"

    def assign(self, name: str, value: Any) -> Any:
        if name in self.values:
            casted = _cast_c_type(value, self.types[name])
            self.values[name] = casted
            return casted
        if self.parent is not None:
            return self.parent.assign(name, value)
        raise NameError(f"Присвоєння неоголошеній змінній '{name}'")


class ASTInterpreter:
    def __init__(self, max_steps: int = 50_000) -> None:
        self.max_steps = max_steps
        self.steps = 0
        self.output_chunks: list[str] = []
        self.functions: dict[str, FunctionDecl] = {}
        self.global_env = Environment()

    def execute(self, program: Program) -> ExecutionResult:
        self.steps = 0
        self.output_chunks = []
        self.functions = {}
        self.global_env = Environment()
        last_main_env_snapshot: dict[str, Any] = {}

        try:
            for decl in program.declarations:
                if isinstance(decl, FunctionDecl):
                    if decl.body is not None:
                        self.functions[decl.name] = decl
                elif isinstance(decl, VarDecl):
                    self._exec_var_decl(decl, self.global_env)

            ret_val: Any = None
            if "main" in self.functions:
                ret_val, last_main_env_snapshot = self._call_user_function(
                    self.functions["main"], [], capture_locals=True
                )

            combined_vars = dict(self.global_env.values)
            for k, v in last_main_env_snapshot.items():
                combined_vars[f"main.{k}"] = v

            return ExecutionResult(
                stdout="".join(self.output_chunks),
                return_value=ret_val,
                variables=combined_vars,
                steps=self.steps,
                error=None,
            )
        except Exception as exc:
            combined_vars = dict(self.global_env.values)
            return ExecutionResult(
                stdout="".join(self.output_chunks),
                return_value=None,
                variables=combined_vars,
                steps=self.steps,
                error=str(exc),
            )

    def _tick(self) -> None:
        self.steps += 1
        if self.steps > self.max_steps:
            raise RuntimeLimitError(f"Перевищено ліміт кроків виконання ({self.max_steps})")

    def _exec_stmt(self, stmt: ASTNode | None, env: Environment) -> None:
        if stmt is None or isinstance(stmt, EmptyStmt):
            return
        self._tick()

        if isinstance(stmt, VarDecl):
            self._exec_var_decl(stmt, env)
        elif isinstance(stmt, Block):
            block_env = Environment(parent=env)
            for s in stmt.statements:
                self._exec_stmt(s, block_env)
        elif isinstance(stmt, ExprStmt):
            self._eval_expr(stmt.expr, env)
        elif isinstance(stmt, IfStmt):
            if self._truthy(self._eval_expr(stmt.condition, env)):
                self._exec_stmt(stmt.then_branch, env)
            elif stmt.else_branch is not None:
                self._exec_stmt(stmt.else_branch, env)
        elif isinstance(stmt, WhileStmt):
            while self._truthy(self._eval_expr(stmt.condition, env)):
                self._tick()
                try:
                    self._exec_stmt(stmt.body, env)
                except _ContinueSignal:
                    continue
                except _BreakSignal:
                    break
        elif isinstance(stmt, DoWhileStmt):
            while True:
                self._tick()
                try:
                    self._exec_stmt(stmt.body, env)
                except _ContinueSignal:
                    pass
                except _BreakSignal:
                    break
                if not self._truthy(self._eval_expr(stmt.condition, env)):
                    break
        elif isinstance(stmt, ForStmt):
            for_env = Environment(parent=env)
            if stmt.init is not None:
                if isinstance(stmt.init, VarDecl):
                    self._exec_var_decl(stmt.init, for_env)
                else:
                    self._eval_expr(stmt.init, for_env)
            while True:
                self._tick()
                if stmt.condition is not None and not self._truthy(self._eval_expr(stmt.condition, for_env)):
                    break
                try:
                    self._exec_stmt(stmt.body, for_env)
                except _ContinueSignal:
                    pass
                except _BreakSignal:
                    break
                if stmt.update is not None:
                    self._eval_expr(stmt.update, for_env)
        elif isinstance(stmt, ReturnStmt):
            val = self._eval_expr(stmt.value, env) if stmt.value is not None else None
            raise _ReturnSignal(val)
        elif isinstance(stmt, BreakStmt):
            raise _BreakSignal()
        elif isinstance(stmt, ContinueStmt):
            raise _ContinueSignal()

    def _exec_var_decl(self, node: VarDecl, env: Environment) -> None:
        for d in node.declarations:
            if d.is_array:
                size = int(self._eval_expr(d.array_size, env)) if d.array_size is not None else None
                if isinstance(d.init, ArrayInitializer):
                    elems = [self._eval_expr(el, env) for el in d.init.elements]
                    if size is not None:
                        if len(elems) < size:
                            elems.extend([_default_value(node.var_type)] * (size - len(elems)))
                        else:
                            elems = elems[:size]
                else:
                    elems = [_default_value(node.var_type)] * (size or 0)
                env.define(d.name, elems, f"{node.var_type}[]")
            else:
                val = self._eval_expr(d.init, env) if d.init is not None else _default_value(node.var_type)
                env.define(d.name, val, node.var_type)

    def _eval_expr(self, expr: ASTNode | None, env: Environment) -> Any:
        if expr is None:
            return None
        self._tick()

        if isinstance(expr, Literal):
            return expr.value

        if isinstance(expr, Identifier):
            return env.get(expr.name)

        if isinstance(expr, ArrayAccess):
            arr = self._eval_expr(expr.array, env)
            idx = int(self._eval_expr(expr.index, env))
            if idx < 0 or idx >= len(arr):
                raise IndexError(f"Вихід за межі масиву (індекс {idx}, розмір {len(arr)}) у рядку {expr.line}")
            return arr[idx]

        if isinstance(expr, Assignment):
            rhs = self._eval_expr(expr.value, env)
            return self._apply_assignment(expr.target, expr.op, rhs, env, expr.line)

        if isinstance(expr, UnaryOp):
            if expr.op in ("++", "--"):
                delta = 1 if expr.op == "++" else -1
                old_val = self._eval_expr(expr.operand, env)
                new_val = self._apply_assignment(expr.operand, "=", old_val + delta, env, expr.line)
                return new_val if expr.prefix else old_val
            val = self._eval_expr(expr.operand, env)
            if expr.op == "+":
                return +val
            if expr.op == "-":
                return -val
            if expr.op == "!":
                return not self._truthy(val)
            if expr.op == "~":
                return ~int(val)

        if isinstance(expr, BinaryOp):
            if expr.op == "&&":
                left = self._eval_expr(expr.left, env)
                return bool(self._truthy(self._eval_expr(expr.right, env))) if self._truthy(left) else False
            if expr.op == "||":
                left = self._eval_expr(expr.left, env)
                return True if self._truthy(left) else bool(self._truthy(self._eval_expr(expr.right, env)))

            left = self._eval_expr(expr.left, env)
            right = self._eval_expr(expr.right, env)
            return self._eval_binary(expr.op, left, right, expr.line)

        if isinstance(expr, FuncCall):
            args = [self._eval_expr(a, env) for a in expr.args]
            if expr.name in self.functions:
                res, _ = self._call_user_function(self.functions[expr.name], args)
                return res
            return self._call_builtin(expr.name, args, expr.line)

        raise RuntimeError(f"Непідтримуваний вузол виразу: {type(expr).__name__}")

    def _apply_assignment(self, target: ASTNode, op: str, rhs: Any, env: Environment, line: int) -> Any:
        if isinstance(target, Identifier):
            if op != "=":
                cur = env.get(target.name)
                rhs = self._eval_binary(op[:-1], cur, rhs, line)
            return env.assign(target.name, rhs)
        if isinstance(target, ArrayAccess):
            arr = self._eval_expr(target.array, env)
            idx = int(self._eval_expr(target.index, env))
            if idx < 0 or idx >= len(arr):
                raise IndexError(f"Вихід за межі масиву (індекс {idx}, розмір {len(arr)}) у рядку {line}")
            if op != "=":
                rhs = self._eval_binary(op[:-1], arr[idx], rhs, line)
            elem_type = target.inferred_type or "int"
            arr[idx] = _cast_c_type(rhs, elem_type)
            return arr[idx]
        raise RuntimeError(f"Некоректний l-value у рядку {line}")

    @staticmethod
    def _eval_binary(op: str, left: Any, right: Any, line: int) -> Any:
        if isinstance(left, str) and len(left) == 1 and isinstance(right, int):
            left = ord(left)
        if isinstance(right, str) and len(right) == 1 and isinstance(left, int):
            right = ord(right)

        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise ZeroDivisionError(f"Ділення на нуль у рядку {line}")
            if isinstance(left, int) and isinstance(right, int) and not isinstance(left, bool) and not isinstance(right, bool):
                return math.trunc(left / right)
            return left / right
        if op == "%":
            if right == 0:
                raise ZeroDivisionError(f"Остача від ділення на нуль у рядку {line}")
            return int(left) % int(right)
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == "<=":
            return left <= right
        if op == ">":
            return left > right
        if op == ">=":
            return left >= right
        if op == "&":
            return int(left) & int(right)
        if op == "|":
            return int(left) | int(right)
        if op == "^":
            return int(left) ^ int(right)
        if op == "<<":
            return int(left) << int(right)
        if op == ">>":
            return int(left) >> int(right)
        raise RuntimeError(f"Невідомий бінарний оператор '{op}'")

    def _call_user_function(
        self,
        func: FunctionDecl,
        args: list[Any],
        capture_locals: bool = False,
    ) -> tuple[Any, dict[str, Any]]:
        func_env = Environment(parent=self.global_env)
        for param, val in zip(func.params, args):
            if param.is_array and isinstance(val, list):
                func_env.values[param.name] = val
                func_env.types[param.name] = f"{param.param_type}[]"
            else:
                func_env.define(param.name, val, param.param_type)

        ret_val: Any = None
        try:
            if func.body is not None:
                for stmt in func.body.statements:
                    self._exec_stmt(stmt, func_env)
        except _ReturnSignal as sig:
            ret_val = _cast_c_type(sig.value, func.return_type) if sig.value is not None and func.return_type != "void" else None

        snapshot = dict(func_env.values) if capture_locals else {}
        return ret_val, snapshot

    def _call_builtin(self, name: str, args: list[Any], line: int) -> Any:
        if name == "printf":
            if not args:
                return 0
            fmt = str(args[0])
            fmt_args = tuple(
                ord(a) if isinstance(a, str) and len(a) == 1 and "%d" in fmt else a
                for a in args[1:]
            )
            try:
                rendered = fmt % fmt_args if fmt_args else fmt
            except TypeError:
                rendered = fmt + " " + " ".join(str(x) for x in fmt_args)
            self.output_chunks.append(rendered)
            return len(rendered)
        if name == "puts":
            text = str(args[0]) + "\n"
            self.output_chunks.append(text)
            return len(text)
        if name == "putchar":
            ch = chr(int(args[0])) if isinstance(args[0], int) else str(args[0])[0]
            self.output_chunks.append(ch)
            return ord(ch)
        if name == "abs":
            return abs(int(args[0]))
        if name == "fabs":
            return abs(float(args[0]))
        if name == "sqrt":
            return math.sqrt(float(args[0]))
        if name == "pow":
            return math.pow(float(args[0]), float(args[1]))
        raise NameError(f"Невідома функція '{name}' у рядку {line}")

    @staticmethod
    def _truthy(val: Any) -> bool:
        return bool(val)
