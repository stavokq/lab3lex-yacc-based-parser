from __future__ import annotations
from dataclasses import dataclass
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


NUMERIC_TYPES = {"int", "float", "double", "char", "bool"}


@dataclass
class Symbol:
    name: str
    kind: str
    data_type: str
    scope: str
    line: int
    is_const: bool = False
    params: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "type": self.data_type,
            "scope": self.scope,
            "line": self.line,
            "isConst": self.is_const,
            "params": self.params,
        }


@dataclass
class SemanticIssue:
    severity: str
    message: str
    line: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SemanticError" if self.severity == "error" else "SemanticWarning",
            "severity": self.severity,
            "message": self.message,
            "line": self.line,
            "column": 1,
        }


BUILTIN_FUNCTIONS: dict[str, tuple[str, list[str] | None]] = {
    "printf": ("int", None),
    "putchar": ("int", ["int"]),
    "puts": ("int", ["string"]),
    "abs": ("int", ["int"]),
    "fabs": ("double", ["double"]),
    "sqrt": ("double", ["double"]),
    "pow": ("double", ["double", "double"]),
}


class SemanticAnalyzer:
    def __init__(self) -> None:
        self.scopes: list[tuple[str, dict[str, Symbol]]] = []
        self.all_symbols: list[Symbol] = []
        self.issues: list[SemanticIssue] = []
        self.current_function: FunctionDecl | None = None
        self.loop_depth: int = 0
        self._block_counter: int = 0

    def analyze(self, program: Program) -> tuple[list[Symbol], list[SemanticIssue]]:
        self.scopes = []
        self.all_symbols = []
        self.issues = []
        self.current_function = None
        self.loop_depth = 0
        self._block_counter = 0

        self._push_scope("global")
        for decl in program.declarations:
            self._visit(decl)
        self._pop_scope()
        return self.all_symbols, self.issues

    def _push_scope(self, name: str) -> None:
        self.scopes.append((name, {}))

    def _pop_scope(self) -> None:
        self.scopes.pop()

    @property
    def _current_scope_name(self) -> str:
        return self.scopes[-1][0]

    def _declare(self, sym: Symbol) -> None:
        current_table = self.scopes[-1][1]
        existing = current_table.get(sym.name)
        if existing is not None:
            if existing.kind == "function" and sym.kind == "function":
                current_table[sym.name] = sym
                return
            self.issues.append(
                SemanticIssue(
                    severity="error",
                    message=f"Повторне оголошення ідентифікатора '{sym.name}' в області '{self._current_scope_name}' (попереднє у рядку {existing.line})",
                    line=sym.line,
                )
            )
            return
        current_table[sym.name] = sym
        self.all_symbols.append(sym)

    def _lookup(self, name: str) -> Symbol | None:
        for _, table in reversed(self.scopes):
            if name in table:
                return table[name]
        return None

    def _visit(self, node: ASTNode | None) -> str:
        if node is None:
            return "void"
        method_name = f"_visit_{type(node).__name__}"
        visitor = getattr(self, method_name, self._visit_generic)
        inferred = visitor(node)
        node.inferred_type = inferred
        return inferred

    def _visit_generic(self, node: ASTNode) -> str:
        return "void"

    def _visit_FunctionDecl(self, node: FunctionDecl) -> str:
        param_types = [f"{p.param_type}{'[]' if p.is_array else ''}" for p in node.params]
        self._declare(
            Symbol(
                name=node.name,
                kind="function",
                data_type=node.return_type,
                scope=self._current_scope_name,
                line=node.line,
                params=param_types,
            )
        )
        if node.body is not None:
            prev_func = self.current_function
            self.current_function = node
            self._push_scope(f"func:{node.name}")
            for p in node.params:
                p_type = f"{p.param_type}[]" if p.is_array else p.param_type
                p.inferred_type = p_type
                self._declare(
                    Symbol(
                        name=p.name,
                        kind="parameter",
                        data_type=p_type,
                        scope=self._current_scope_name,
                        line=p.line,
                    )
                )
            for stmt in node.body.statements:
                self._visit(stmt)
            self._pop_scope()
            self.current_function = prev_func
        return node.return_type

    def _visit_VarDecl(self, node: VarDecl) -> str:
        if node.var_type == "void":
            self.issues.append(
                SemanticIssue("error", "Змінна не може мати тип 'void'", node.line)
            )
        for decl in node.declarations:
            full_type = f"{node.var_type}[]" if decl.is_array else node.var_type
            decl.inferred_type = full_type
            if decl.array_size is not None:
                sz_type = self._visit(decl.array_size)
                if sz_type not in ("int", "char"):
                    self.issues.append(
                        SemanticIssue("error", f"Розмір масиву '{decl.name}' має бути цілим числом, отримано '{sz_type}'", decl.line)
                    )
            if decl.init is not None:
                init_type = self._visit(decl.init)
                if not decl.is_array and isinstance(decl.init, ArrayInitializer):
                    self.issues.append(
                        SemanticIssue("error", f"Скалярну змінну '{decl.name}' не можна ініціалізувати списком {{...}}", decl.line)
                    )
                elif not decl.is_array and not self._types_compatible(node.var_type, init_type):
                    self.issues.append(
                        SemanticIssue("warning", f"Неявне або несумісне приведення типу '{init_type}' до '{node.var_type}' при ініціалізації '{decl.name}'", decl.line)
                    )
            self._declare(
                Symbol(
                    name=decl.name,
                    kind="array" if decl.is_array else "variable",
                    data_type=full_type,
                    scope=self._current_scope_name,
                    line=decl.line,
                    is_const=node.is_const,
                )
            )
        return node.var_type

    def _visit_ArrayInitializer(self, node: ArrayInitializer) -> str:
        elem_type = "int"
        for el in node.elements:
            elem_type = self._visit(el)
        return f"{elem_type}[]"

    def _visit_Block(self, node: Block) -> str:
        self._block_counter += 1
        self._push_scope(f"block#{self._block_counter}")
        for stmt in node.statements:
            self._visit(stmt)
        self._pop_scope()
        return "void"

    def _visit_IfStmt(self, node: IfStmt) -> str:
        self._visit(node.condition)
        self._visit(node.then_branch)
        if node.else_branch is not None:
            self._visit(node.else_branch)
        return "void"

    def _visit_WhileStmt(self, node: WhileStmt) -> str:
        self._visit(node.condition)
        self.loop_depth += 1
        self._visit(node.body)
        self.loop_depth -= 1
        return "void"

    def _visit_DoWhileStmt(self, node: DoWhileStmt) -> str:
        self.loop_depth += 1
        self._visit(node.body)
        self.loop_depth -= 1
        self._visit(node.condition)
        return "void"

    def _visit_ForStmt(self, node: ForStmt) -> str:
        self._block_counter += 1
        self._push_scope(f"for#{self._block_counter}")
        if node.init is not None:
            self._visit(node.init)
        if node.condition is not None:
            self._visit(node.condition)
        if node.update is not None:
            self._visit(node.update)
        self.loop_depth += 1
        self._visit(node.body)
        self.loop_depth -= 1
        self._pop_scope()
        return "void"

    def _visit_ReturnStmt(self, node: ReturnStmt) -> str:
        ret_type = self._visit(node.value) if node.value is not None else "void"
        if self.current_function is not None:
            expected = self.current_function.return_type
            if expected == "void" and node.value is not None:
                self.issues.append(
                    SemanticIssue("error", f"Функція '{self.current_function.name}' з типом 'void' не повинна повертати значення", node.line)
                )
            elif expected != "void" and node.value is None:
                self.issues.append(
                    SemanticIssue("error", f"Функція '{self.current_function.name}' повинна повертати значення типу '{expected}'", node.line)
                )
        return ret_type

    def _visit_BreakStmt(self, node: BreakStmt) -> str:
        if self.loop_depth == 0:
            self.issues.append(SemanticIssue("error", "Оператор 'break' використано поза межами циклу", node.line))
        return "void"

    def _visit_ContinueStmt(self, node: ContinueStmt) -> str:
        if self.loop_depth == 0:
            self.issues.append(SemanticIssue("error", "Оператор 'continue' використано поза межами циклу", node.line))
        return "void"

    def _visit_EmptyStmt(self, node: EmptyStmt) -> str:
        return "void"

    def _visit_ExprStmt(self, node: ExprStmt) -> str:
        return self._visit(node.expr)

    def _visit_Assignment(self, node: Assignment) -> str:
        if not isinstance(node.target, (Identifier, ArrayAccess)):
            self.issues.append(
                SemanticIssue("error", "Ліва частина присвоєння не є l-value", node.line)
            )
            lhs_type = "error"
        else:
            lhs_type = self._visit(node.target)
            if isinstance(node.target, Identifier):
                sym = self._lookup(node.target.name)
                if sym and sym.is_const:
                    self.issues.append(
                        SemanticIssue("error", f"Неможливо змінити значення константи '{node.target.name}'", node.line)
                    )
                if sym and sym.kind == "array":
                    self.issues.append(
                        SemanticIssue("error", f"Неможливо присвоїти значення безпосередньо масиву '{node.target.name}'", node.line)
                    )
        rhs_type = self._visit(node.value)
        if lhs_type not in ("error", "unknown") and rhs_type not in ("error", "unknown"):
            if not self._types_compatible(lhs_type, rhs_type):
                self.issues.append(
                    SemanticIssue("warning", f"Несумісні типи у присвоєнні: '{lhs_type}' та '{rhs_type}'", node.line)
                )
        return lhs_type

    def _visit_BinaryOp(self, node: BinaryOp) -> str:
        lt = self._visit(node.left)
        rt = self._visit(node.right)
        if node.op in ("==", "!=", "<", "<=", ">", ">=", "&&", "||"):
            return "bool"
        if "double" in (lt, rt):
            return "double"
        if "float" in (lt, rt):
            return "float"
        return "int"

    def _visit_UnaryOp(self, node: UnaryOp) -> str:
        ot = self._visit(node.operand)
        if node.op in ("++", "--"):
            if not isinstance(node.operand, (Identifier, ArrayAccess)):
                self.issues.append(
                    SemanticIssue("error", f"Оператор '{node.op}' вимагає l-value", node.line)
                )
            elif isinstance(node.operand, Identifier):
                sym = self._lookup(node.operand.name)
                if sym and sym.is_const:
                    self.issues.append(
                        SemanticIssue("error", f"Неможливо застосувати '{node.op}' до константи '{node.operand.name}'", node.line)
                    )
        if node.op == "!":
            return "bool"
        return ot

    def _visit_FuncCall(self, node: FuncCall) -> str:
        arg_types = [self._visit(a) for a in node.args]
        sym = self._lookup(node.name)
        if sym is not None and sym.kind == "function":
            expected = sym.params or []
            if len(arg_types) != len(expected):
                self.issues.append(
                    SemanticIssue(
                        "error",
                        f"Функція '{node.name}' очікує аргументів: {len(expected)}, передано: {len(arg_types)}",
                        node.line,
                    )
                )
            return sym.data_type
        if node.name in BUILTIN_FUNCTIONS:
            ret_type, expected = BUILTIN_FUNCTIONS[node.name]
            if expected is not None and len(arg_types) != len(expected):
                self.issues.append(
                    SemanticIssue(
                        "error",
                        f"Стандартна функція '{node.name}' очікує аргументів: {len(expected)}, передано: {len(arg_types)}",
                        node.line,
                    )
                )
            return ret_type
        self.issues.append(
            SemanticIssue("error", f"Виклик неоголошеної функції '{node.name}'", node.line)
        )
        return "unknown"

    def _visit_ArrayAccess(self, node: ArrayAccess) -> str:
        arr_type = self._visit(node.array)
        idx_type = self._visit(node.index)
        if idx_type not in ("int", "char", "bool", "unknown"):
            self.issues.append(
                SemanticIssue("error", f"Індекс масиву має бути цілим числом, отримано '{idx_type}'", node.line)
            )
        if arr_type.endswith("[]"):
            return arr_type[:-2]
        if arr_type == "string":
            return "char"
        if arr_type != "unknown":
            self.issues.append(
                SemanticIssue("error", f"Спроба індексації виразу типу '{arr_type}', що не є масивом", node.line)
            )
        return "unknown"

    def _visit_Identifier(self, node: Identifier) -> str:
        sym = self._lookup(node.name)
        if sym is None:
            self.issues.append(
                SemanticIssue("error", f"Використання неоголошеної змінної '{node.name}'", node.line)
            )
            return "unknown"
        return sym.data_type

    def _visit_Literal(self, node: Literal) -> str:
        return node.literal_type

    @staticmethod
    def _types_compatible(target: str, source: str) -> bool:
        if target == source:
            return True
        if target in NUMERIC_TYPES and source in NUMERIC_TYPES:
            return True
        return False
