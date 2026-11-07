from __future__ import annotations
import os
import subprocess
import sys
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


C_TO_PY_TYPE: dict[str, str] = {
    "int": "int",
    "float": "float",
    "double": "float",
    "char": "str",
    "bool": "bool",
    "void": "None",
    "string": "str",
}

PY_OP_PRECEDENCE: dict[str, int] = {
    "or": 1,
    "and": 2,
    "not": 3,
    "==": 4,
    "!=": 4,
    "<": 4,
    "<=": 4,
    ">": 4,
    ">=": 4,
    "|": 5,
    "^": 6,
    "&": 7,
    "<<": 8,
    ">>": 8,
    "+": 9,
    "-": 9,
    "*": 10,
    "/": 10,
    "//": 10,
    "%": 10,
}


class PythonCodeGenerator:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.indent_level: int = 0
        self.global_vars: set[str] = set()
        self.needs_math: bool = False
        self.has_main: bool = False
        self.loop_updates: list[ASTNode | None] = []
        self._pre_stmts: list[str] = []
        self._post_stmts: list[str] = []

    def generate(self, program: Program) -> str:
        self.lines = []
        self.indent_level = 0
        self.global_vars = set()
        self.needs_math = False
        self.has_main = False
        self.loop_updates = []

        self._scan_program(program)

        header: list[str] = []
        if self.needs_math:
            header.append("import math")
            header.append("")

        for decl in program.declarations:
            if isinstance(decl, VarDecl):
                self._emit_var_decl(decl)
                self._emit("")
            elif isinstance(decl, FunctionDecl):
                if decl.body is not None:
                    self._emit_function(decl)
                    self._emit("")

        if self.has_main:
            self._emit('if __name__ == "__main__":')
            self.indent_level += 1
            self._emit("main()")
            self.indent_level -= 1

        body_text = "\n".join(self.lines).rstrip() + "\n"
        if header:
            return "\n".join(header) + "\n" + body_text
        return body_text

    def _scan_program(self, program: Program) -> None:
        for decl in program.declarations:
            if isinstance(decl, VarDecl):
                for d in decl.declarations:
                    self.global_vars.add(d.name)
            elif isinstance(decl, FunctionDecl) and decl.body is not None:
                if decl.name == "main":
                    self.has_main = True
        self._check_math_usage(program)

    def _check_math_usage(self, node: Any) -> None:
        if isinstance(node, FuncCall) and node.name in ("sqrt", "pow", "fabs"):
            self.needs_math = True
        if isinstance(node, ASTNode):
            for val in node.__dict__.values():
                if isinstance(val, ASTNode):
                    self._check_math_usage(val)
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, ASTNode):
                            self._check_math_usage(item)

    def _collect_local_and_modified_vars(self, block: Block, params: set[str]) -> tuple[set[str], set[str]]:
        locals_set = set(params)
        modified_set: set[str] = set()

        def walk(n: Any) -> None:
            if isinstance(n, VarDecl):
                for d in n.declarations:
                    locals_set.add(d.name)
            elif isinstance(n, Assignment) and isinstance(n.target, Identifier):
                modified_set.add(n.target.name)
            elif isinstance(n, UnaryOp) and n.op in ("++", "--") and isinstance(n.operand, Identifier):
                modified_set.add(n.operand.name)

            if isinstance(n, ASTNode):
                for v in n.__dict__.values():
                    if isinstance(v, ASTNode):
                        walk(v)
                    elif isinstance(v, list):
                        for item in v:
                            if isinstance(item, ASTNode):
                                walk(item)

        walk(block)
        return locals_set, modified_set

    def _emit(self, line: str = "") -> None:
        if line == "":
            self.lines.append("")
        else:
            self.lines.append("    " * self.indent_level + line)

    def _flush_pre_stmts(self) -> None:
        while self._pre_stmts:
            self._emit(self._pre_stmts.pop(0))

    def _flush_post_stmts(self) -> None:
        while self._post_stmts:
            self._emit(self._post_stmts.pop(0))

    @staticmethod
    def _py_type(c_type: str, is_array: bool = False) -> str:
        clean = c_type.replace("[]", "")
        base = C_TO_PY_TYPE.get(clean, "Any")
        if is_array or c_type.endswith("[]"):
            return f"list[{base}]"
        return base

    @staticmethod
    def _default_literal(c_type: str) -> str:
        if c_type in ("float", "double"):
            return "0.0"
        if c_type == "bool":
            return "False"
        if c_type == "char":
            return "'\\x00'"
        return "0"

    def _emit_function(self, func: FunctionDecl) -> None:
        params_str = ", ".join(
            f"{p.name}: {self._py_type(p.param_type, p.is_array)}" for p in func.params
        )
        ret_str = self._py_type(func.return_type)
        self._emit(f"def {func.name}({params_str}) -> {ret_str}:")
        self.indent_level += 1

        assert func.body is not None
        param_names = {p.name for p in func.params}
        locals_set, modified_set = self._collect_local_and_modified_vars(func.body, param_names)
        globals_used = sorted((modified_set & self.global_vars) - locals_set)
        if globals_used:
            self._emit(f"global {', '.join(globals_used)}")

        if not func.body.statements and not globals_used:
            self._emit("pass")
        else:
            for stmt in func.body.statements:
                self._emit_stmt(stmt)

        self.indent_level -= 1

    def _emit_var_decl(self, node: VarDecl) -> None:
        for d in node.declarations:
            py_t = self._py_type(node.var_type, d.is_array)
            if d.is_array:
                if isinstance(d.init, ArrayInitializer):
                    elems = [self._expr(el) for el in d.init.elements]
                    self._flush_pre_stmts()
                    init_code = f"[{', '.join(elems)}]"
                    if d.array_size is not None:
                        sz = self._expr(d.array_size)
                        if len(elems) == 0:
                            init_code = f"[{self._default_literal(node.var_type)}] * {sz}"
                    self._emit(f"{d.name}: {py_t} = {init_code}")
                    self._flush_post_stmts()
                else:
                    sz = self._expr(d.array_size) if d.array_size is not None else "0"
                    self._flush_pre_stmts()
                    self._emit(f"{d.name}: {py_t} = [{self._default_literal(node.var_type)}] * {sz}")
                    self._flush_post_stmts()
            else:
                val_str = self._expr(d.init) if d.init is not None else self._default_literal(node.var_type)
                self._flush_pre_stmts()
                self._emit(f"{d.name}: {py_t} = {val_str}")
                self._flush_post_stmts()

    def _emit_stmt(self, stmt: ASTNode | None) -> None:
        if stmt is None or isinstance(stmt, EmptyStmt):
            return

        if isinstance(stmt, VarDecl):
            self._emit_var_decl(stmt)
        elif isinstance(stmt, Block):
            if not stmt.statements:
                self._emit("pass")
            else:
                for s in stmt.statements:
                    self._emit_stmt(s)
        elif isinstance(stmt, ExprStmt):
            self._emit_expr_as_stmt(stmt.expr)
        elif isinstance(stmt, IfStmt):
            self._emit_if(stmt, keyword="if")
        elif isinstance(stmt, WhileStmt):
            cond_str = self._expr(stmt.condition)
            self._flush_pre_stmts()
            self._emit(f"while {cond_str}:")
            self._flush_post_stmts()
            self.indent_level += 1
            self.loop_updates.append(None)
            self._emit_loop_body(stmt.body)
            self.loop_updates.pop()
            self.indent_level -= 1
        elif isinstance(stmt, DoWhileStmt):
            self._emit("while True:")
            self.indent_level += 1
            self.loop_updates.append(None)
            self._emit_loop_body(stmt.body)
            self.loop_updates.pop()
            cond_str = self._expr(stmt.condition)
            self._flush_pre_stmts()
            self._emit(f"if not ({cond_str}):")
            self._flush_post_stmts()
            self.indent_level += 1
            self._emit("break")
            self.indent_level -= 1
            self.indent_level -= 1
        elif isinstance(stmt, ForStmt):
            if stmt.init is not None:
                if isinstance(stmt.init, VarDecl):
                    self._emit_var_decl(stmt.init)
                else:
                    self._emit_expr_as_stmt(stmt.init)
            cond_str = self._expr(stmt.condition) if stmt.condition is not None else "True"
            self._flush_pre_stmts()
            self._emit(f"while {cond_str}:")
            self._flush_post_stmts()
            self.indent_level += 1
            self.loop_updates.append(stmt.update)
            self._emit_loop_body(stmt.body)
            self.loop_updates.pop()
            if stmt.update is not None:
                self._emit_expr_as_stmt(stmt.update)
            self.indent_level -= 1
        elif isinstance(stmt, ReturnStmt):
            if stmt.value is not None:
                val_str = self._expr(stmt.value)
                self._flush_pre_stmts()
                self._emit(f"return {val_str}")
                self._flush_post_stmts()
            else:
                self._emit("return")
        elif isinstance(stmt, BreakStmt):
            self._emit("break")
        elif isinstance(stmt, ContinueStmt):
            if self.loop_updates and self.loop_updates[-1] is not None:
                self._emit_expr_as_stmt(self.loop_updates[-1])
            self._emit("continue")

    def _emit_loop_body(self, body: ASTNode) -> None:
        if isinstance(body, Block):
            if not body.statements:
                self._emit("pass")
            else:
                for s in body.statements:
                    self._emit_stmt(s)
        else:
            self._emit_stmt(body)

    def _emit_if(self, node: IfStmt, keyword: str = "if") -> None:
        cond_str = self._expr(node.condition)
        self._flush_pre_stmts()
        self._emit(f"{keyword} {cond_str}:")
        self._flush_post_stmts()
        self.indent_level += 1
        self._emit_loop_body(node.then_branch)
        self.indent_level -= 1

        if node.else_branch is not None:
            if isinstance(node.else_branch, IfStmt):
                self._emit_if(node.else_branch, keyword="elif")
            else:
                self._emit("else:")
                self.indent_level += 1
                self._emit_loop_body(node.else_branch)
                self.indent_level -= 1

    def _emit_expr_as_stmt(self, expr: ASTNode) -> None:
        if isinstance(expr, UnaryOp) and expr.op in ("++", "--"):
            target = self._expr(expr.operand)
            op = "+=" if expr.op == "++" else "-="
            self._flush_pre_stmts()
            self._emit(f"{target} {op} 1")
            self._flush_post_stmts()
            return

        if isinstance(expr, Assignment):
            target = self._expr(expr.target)
            rhs = self._expr(expr.value)
            op = expr.op
            if op == "/=" and self._is_int_node(expr.target) and self._is_int_node(expr.value):
                op = "//="
            self._flush_pre_stmts()
            self._emit(f"{target} {op} {rhs}")
            self._flush_post_stmts()
            return

        code = self._expr(expr)
        self._flush_pre_stmts()
        self._emit(code)
        self._flush_post_stmts()

    def _expr(self, node: ASTNode | None, parent_prec: int = 0, is_right_child: bool = False) -> str:
        if node is None:
            return "None"

        if isinstance(node, Literal):
            if node.literal_type == "bool":
                return "True" if node.value else "False"
            if node.literal_type in ("string", "char"):
                return repr(node.value)
            return str(node.value)

        if isinstance(node, Identifier):
            return node.name

        if isinstance(node, ArrayAccess):
            arr_s = self._expr(node.array, parent_prec=20)
            idx_s = self._expr(node.index, parent_prec=0)
            return f"{arr_s}[{idx_s}]"

        if isinstance(node, FuncCall):
            return self._translate_call(node)

        if isinstance(node, UnaryOp):
            if node.op in ("++", "--"):
                target = self._expr(node.operand)
                step = f"{target} += 1" if node.op == "++" else f"{target} -= 1"
                if node.prefix:
                    self._pre_stmts.append(step)
                else:
                    self._post_stmts.append(step)
                return target
            operand_s = self._expr(node.operand, parent_prec=12)
            if node.op == "!":
                res = f"not {self._expr(node.operand, parent_prec=PY_OP_PRECEDENCE['not'])}"
                return f"({res})" if parent_prec > PY_OP_PRECEDENCE["not"] else res
            return f"{node.op}{operand_s}"

        if isinstance(node, Assignment):
            target = self._expr(node.target)
            rhs = self._expr(node.value)
            op = "//=" if (node.op == "/=" and self._is_int_node(node.target) and self._is_int_node(node.value)) else node.op
            self._pre_stmts.append(f"{target} {op} {rhs}")
            return target

        if isinstance(node, BinaryOp):
            py_op = self._map_binary_op(node)
            my_prec = PY_OP_PRECEDENCE.get(py_op, 10)
            left_s = self._expr(node.left, parent_prec=my_prec, is_right_child=False)
            right_s = self._expr(node.right, parent_prec=my_prec, is_right_child=True)
            expr_s = f"{left_s} {py_op} {right_s}"
            need_parens = my_prec < parent_prec or (
                my_prec == parent_prec and is_right_child and py_op in ("-", "/", "//", "%")
            )
            return f"({expr_s})" if need_parens else expr_s

        return "None"

    def _map_binary_op(self, node: BinaryOp) -> str:
        if node.op == "&&":
            return "and"
        if node.op == "||":
            return "or"
        if node.op == "/" and self._is_int_node(node.left) and self._is_int_node(node.right):
            return "//"
        return node.op

    @staticmethod
    def _is_int_node(node: ASTNode) -> bool:
        return (node.inferred_type or "") in ("int", "char", "bool")

    def _translate_call(self, call: FuncCall) -> str:
        if call.name == "printf":
            if not call.args:
                return 'print("", end="")'
            first = call.args[0]
            single_arg_prec = 11 if len(call.args) == 2 else 0
            rest = [self._expr(a, parent_prec=single_arg_prec) for a in call.args[1:]]
            if isinstance(first, Literal) and first.literal_type == "string":
                raw_fmt: str = first.value
                ends_nl = raw_fmt.endswith("\n")
                trimmed = raw_fmt[:-1] if ends_nl else raw_fmt
                fmt_repr = repr(trimmed)
                if not rest:
                    return f"print({fmt_repr})" if ends_nl else f'print({fmt_repr}, end="")'
                args_part = rest[0] if len(rest) == 1 else f"({', '.join(rest)})"
                if ends_nl:
                    return f"print({fmt_repr} % {args_part})"
                return f'print({fmt_repr} % {args_part}, end="")'
            fmt_expr = self._expr(first)
            if not rest:
                return f'print({fmt_expr}, end="")'
            return f'print({fmt_expr} % ({", ".join(rest)}), end="")'

        if call.name == "puts":
            arg = self._expr(call.args[0]) if call.args else '""'
            return f"print({arg})"

        if call.name == "putchar":
            arg = self._expr(call.args[0]) if call.args else "''"
            return f'print(chr({arg}) if isinstance({arg}, int) else {arg}, end="")'

        if call.name == "fabs":
            arg = self._expr(call.args[0])
            return f"math.fabs({arg})"

        if call.name == "sqrt":
            arg = self._expr(call.args[0])
            return f"math.sqrt({arg})"

        if call.name == "pow":
            a1 = self._expr(call.args[0])
            a2 = self._expr(call.args[1])
            return f"math.pow({a1}, {a2})"

        args_str = ", ".join(self._expr(a) for a in call.args)
        return f"{call.name}({args_str})"


def run_generated_python(py_code: str, timeout_sec: float = 3.0) -> dict[str, Any]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(
            [sys.executable, "-c", py_code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_sec,
            env=env,
        )
        return {
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "exitCode": proc.returncode,
            "timedOut": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "stdout": exc.stdout or "",
            "stderr": f"Перевищено час очікування виконання ({timeout_sec} с)",
            "exitCode": -1,
            "timedOut": True,
        }
