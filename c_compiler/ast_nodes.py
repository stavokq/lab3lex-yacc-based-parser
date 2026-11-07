from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ASTNode:
    line: int = field(default=0, kw_only=True)
    inferred_type: str | None = field(default=None, kw_only=True)

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    def count_nodes(self) -> int:
        return _count_dict_nodes(self.to_dict())


def _count_dict_nodes(node_dict: dict[str, Any]) -> int:
    total = 1
    for child in node_dict.get("children", []):
        total += _count_dict_nodes(child)
    return total


def _make_node(
    label: str,
    node_type: str,
    category: str,
    line: int = 0,
    details: str = "",
    inferred_type: str | None = None,
    children: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "name": label,
        "nodeType": node_type,
        "category": category,
        "line": line,
        "details": details,
        "inferredType": inferred_type,
        "children": children or [],
    }


@dataclass
class Program(ASTNode):
    declarations: list[ASTNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label="Program",
            node_type="Program",
            category="program",
            line=self.line or 1,
            details=f"оголошень: {len(self.declarations)}",
            children=[d.to_dict() for d in self.declarations],
        )


@dataclass
class Param(ASTNode):
    param_type: str
    name: str
    is_array: bool = False

    def to_dict(self) -> dict[str, Any]:
        arr_suffix = "[]" if self.is_array else ""
        full_type = f"{self.param_type}{arr_suffix}"
        return _make_node(
            label=f"Param: {self.name}",
            node_type="Param",
            category="declaration",
            line=self.line,
            inferred_type=full_type,
        )


@dataclass
class FunctionDecl(ASTNode):
    return_type: str
    name: str
    params: list[Param]
    body: Block | None = None

    def to_dict(self) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        if self.params:
            children.append(
                _make_node(
                    label="Params",
                    node_type="ParamList",
                    category="declaration",
                    line=self.line,
                    children=[p.to_dict() for p in self.params],
                )
            )
        if self.body is not None:
            children.append(self.body.to_dict())
        sig = ", ".join(f"{p.param_type}{'[]' if p.is_array else ''} {p.name}" for p in self.params)
        return _make_node(
            label=f"Func: {self.return_type} {self.name}()",
            node_type="FunctionDecl",
            category="program",
            line=self.line,
            details=f"{self.return_type} {self.name}({sig})",
            inferred_type=self.return_type,
            children=children,
        )


@dataclass
class ArrayInitializer(ASTNode):
    elements: list[ASTNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label=f"ArrayInit [{len(self.elements)}]",
            node_type="ArrayInitializer",
            category="literal",
            line=self.line,
            inferred_type=self.inferred_type,
            children=[el.to_dict() for el in self.elements],
        )


@dataclass
class VarInit(ASTNode):
    name: str
    init: ASTNode | None = None
    array_size: ASTNode | None = None
    is_array: bool = False

    def to_dict(self) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        if self.array_size is not None:
            size_node = self.array_size.to_dict()
            size_node["name"] = f"Size: {size_node['name']}"
            children.append(size_node)
        if self.init is not None:
            children.append(self.init.to_dict())
        suffix = "[]" if self.is_array else ""
        return _make_node(
            label=f"{self.name}{suffix}" + (" =" if self.init else ""),
            node_type="VarInit",
            category="declaration",
            line=self.line,
            inferred_type=self.inferred_type,
            children=children,
        )


@dataclass
class VarDecl(ASTNode):
    var_type: str
    declarations: list[VarInit]
    is_const: bool = False

    def to_dict(self) -> dict[str, Any]:
        prefix = "const " if self.is_const else ""
        names = ", ".join(d.name + ("[]" if d.is_array else "") for d in self.declarations)
        return _make_node(
            label=f"VarDecl: {prefix}{self.var_type}",
            node_type="VarDecl",
            category="declaration",
            line=self.line,
            details=names,
            inferred_type=self.var_type,
            children=[d.to_dict() for d in self.declarations],
        )


@dataclass
class Block(ASTNode):
    statements: list[ASTNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label=f"Block ({len(self.statements)})",
            node_type="Block",
            category="control",
            line=self.line,
            children=[s.to_dict() for s in self.statements],
        )


@dataclass
class IfStmt(ASTNode):
    condition: ASTNode
    then_branch: ASTNode
    else_branch: ASTNode | None = None

    def to_dict(self) -> dict[str, Any]:
        cond_dict = _make_node(
            label="Condition",
            node_type="Condition",
            category="control",
            line=self.condition.line,
            children=[self.condition.to_dict()],
        )
        then_dict = _make_node(
            label="Then",
            node_type="ThenBranch",
            category="control",
            line=self.then_branch.line,
            children=[self.then_branch.to_dict()],
        )
        children = [cond_dict, then_dict]
        if self.else_branch is not None:
            else_dict = _make_node(
                label="Else",
                node_type="ElseBranch",
                category="control",
                line=self.else_branch.line,
                children=[self.else_branch.to_dict()],
            )
            children.append(else_dict)
        return _make_node(
            label="If" + ("-Else" if self.else_branch else ""),
            node_type="IfStmt",
            category="control",
            line=self.line,
            children=children,
        )


@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode
    body: ASTNode

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label="While",
            node_type="WhileStmt",
            category="control",
            line=self.line,
            children=[
                _make_node("Condition", "Condition", "control", self.condition.line, children=[self.condition.to_dict()]),
                _make_node("Body", "LoopBody", "control", self.body.line, children=[self.body.to_dict()]),
            ],
        )


@dataclass
class DoWhileStmt(ASTNode):
    body: ASTNode
    condition: ASTNode

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label="Do-While",
            node_type="DoWhileStmt",
            category="control",
            line=self.line,
            children=[
                _make_node("Body", "LoopBody", "control", self.body.line, children=[self.body.to_dict()]),
                _make_node("Condition", "Condition", "control", self.condition.line, children=[self.condition.to_dict()]),
            ],
        )


@dataclass
class ForStmt(ASTNode):
    init: ASTNode | None
    condition: ASTNode | None
    update: ASTNode | None
    body: ASTNode

    def to_dict(self) -> dict[str, Any]:
        children: list[dict[str, Any]] = []
        if self.init is not None:
            children.append(_make_node("Init", "ForInit", "control", self.init.line, children=[self.init.to_dict()]))
        if self.condition is not None:
            children.append(_make_node("Condition", "Condition", "control", self.condition.line, children=[self.condition.to_dict()]))
        if self.update is not None:
            children.append(_make_node("Update", "ForUpdate", "control", self.update.line, children=[self.update.to_dict()]))
        children.append(_make_node("Body", "LoopBody", "control", self.body.line, children=[self.body.to_dict()]))
        return _make_node(
            label="For",
            node_type="ForStmt",
            category="control",
            line=self.line,
            children=children,
        )


@dataclass
class ReturnStmt(ASTNode):
    value: ASTNode | None = None

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label="Return",
            node_type="ReturnStmt",
            category="control",
            line=self.line,
            inferred_type=self.inferred_type,
            children=[self.value.to_dict()] if self.value else [],
        )


@dataclass
class BreakStmt(ASTNode):
    def to_dict(self) -> dict[str, Any]:
        return _make_node("Break", "BreakStmt", "control", self.line)


@dataclass
class ContinueStmt(ASTNode):
    def to_dict(self) -> dict[str, Any]:
        return _make_node("Continue", "ContinueStmt", "control", self.line)


@dataclass
class EmptyStmt(ASTNode):
    def to_dict(self) -> dict[str, Any]:
        return _make_node("Empty ;", "EmptyStmt", "control", self.line)


@dataclass
class ExprStmt(ASTNode):
    expr: ASTNode

    def to_dict(self) -> dict[str, Any]:
        return self.expr.to_dict()


@dataclass
class Assignment(ASTNode):
    target: ASTNode
    op: str
    value: ASTNode

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label=f"Assign ({self.op})",
            node_type="Assignment",
            category="expression",
            line=self.line,
            inferred_type=self.inferred_type,
            children=[self.target.to_dict(), self.value.to_dict()],
        )


@dataclass
class BinaryOp(ASTNode):
    op: str
    left: ASTNode
    right: ASTNode

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label=f"Op ({self.op})",
            node_type="BinaryOp",
            category="expression",
            line=self.line,
            inferred_type=self.inferred_type,
            children=[self.left.to_dict(), self.right.to_dict()],
        )


@dataclass
class UnaryOp(ASTNode):
    op: str
    operand: ASTNode
    prefix: bool = True

    def to_dict(self) -> dict[str, Any]:
        disp = f"{self.op}x" if self.prefix else f"x{self.op}"
        return _make_node(
            label=f"Unary ({disp})",
            node_type="UnaryOp",
            category="expression",
            line=self.line,
            inferred_type=self.inferred_type,
            children=[self.operand.to_dict()],
        )


@dataclass
class FuncCall(ASTNode):
    name: str
    args: list[ASTNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label=f"Call: {self.name}()",
            node_type="FuncCall",
            category="expression",
            line=self.line,
            details=f"аргументів: {len(self.args)}",
            inferred_type=self.inferred_type,
            children=[a.to_dict() for a in self.args],
        )


@dataclass
class ArrayAccess(ASTNode):
    array: ASTNode
    index: ASTNode

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label="Index []",
            node_type="ArrayAccess",
            category="expression",
            line=self.line,
            inferred_type=self.inferred_type,
            children=[self.array.to_dict(), self.index.to_dict()],
        )


@dataclass
class Identifier(ASTNode):
    name: str

    def to_dict(self) -> dict[str, Any]:
        return _make_node(
            label=f"ID: {self.name}",
            node_type="Identifier",
            category="literal",
            line=self.line,
            inferred_type=self.inferred_type,
        )


@dataclass
class Literal(ASTNode):
    value: Any
    literal_type: str

    def to_dict(self) -> dict[str, Any]:
        if self.literal_type in ("string", "char"):
            shown = repr(self.value)
        elif self.literal_type == "bool":
            shown = "true" if self.value else "false"
        else:
            shown = str(self.value)
        return _make_node(
            label=f"{self.literal_type}: {shown}",
            node_type="Literal",
            category="literal",
            line=self.line,
            inferred_type=self.inferred_type or self.literal_type,
        )
