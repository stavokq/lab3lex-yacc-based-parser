from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any
import ply.yacc as yacc

from .lexer import CLexer, LexError, find_column, tokens
from .ast_nodes import (
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
    Param,
    Program,
    ReturnStmt,
    UnaryOp,
    VarDecl,
    VarInit,
    WhileStmt,
)


@dataclass
class ParseError:
    message: str
    line: int
    column: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "SyntaxError",
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }


class CParser:
    tokens = tokens

    precedence = (
        ("nonassoc", "LOWER_THAN_ELSE"),
        ("nonassoc", "ELSE"),
        ("left", "OR"),
        ("left", "AND"),
        ("left", "BIT_OR"),
        ("left", "BIT_XOR"),
        ("left", "BIT_AND"),
        ("left", "EQ", "NEQ"),
        ("left", "LT", "LE", "GT", "GE"),
        ("left", "LSHIFT", "RSHIFT"),
        ("left", "PLUS", "MINUS"),
        ("left", "TIMES", "DIVIDE", "MOD"),
    )

    def __init__(self, debug_dir: Path | None = None) -> None:
        self.c_lexer = CLexer()
        self.errors: list[ParseError] = []
        self.source_code: str = ""
        self.debug_dir = debug_dir or Path(__file__).resolve().parent.parent
        self.debug_file = self.debug_dir / "parser.out"
        need_regen = (
            not self.debug_file.exists()
            or Path(__file__).stat().st_mtime > self.debug_file.stat().st_mtime
        )
        self.parser = yacc.yacc(
            module=self,
            start="program",
            debug=need_regen,
            debugfile=str(self.debug_file),
            outputdir=str(self.debug_dir),
        )

    def p_program(self, p: yacc.YaccProduction) -> None:
        """program : external_decl_list"""
        first_line = p[1][0].line if p[1] else 1
        p[0] = Program(declarations=p[1], line=first_line)

    def p_external_decl_list(self, p: yacc.YaccProduction) -> None:
        """external_decl_list : external_decl_list external_decl
                              | empty"""
        if len(p) == 3:
            p[0] = p[1] + [p[2]]
        else:
            p[0] = []

    def p_external_decl(self, p: yacc.YaccProduction) -> None:
        """external_decl : func_decl
                         | var_decl"""
        p[0] = p[1]

    def p_type_spec(self, p: yacc.YaccProduction) -> None:
        """type_spec : INT
                     | FLOAT
                     | DOUBLE
                     | CHAR
                     | VOID
                     | BOOL"""
        p[0] = p[1]

    def p_func_decl(self, p: yacc.YaccProduction) -> None:
        """func_decl : type_spec ID LPAREN param_list_opt RPAREN compound_stmt
                     | type_spec ID LPAREN param_list_opt RPAREN SEMI"""
        body = p[6] if isinstance(p[6], Block) else None
        p[0] = FunctionDecl(
            return_type=p[1],
            name=p[2],
            params=p[4],
            body=body,
            line=p.lineno(2),
        )

    def p_param_list_opt(self, p: yacc.YaccProduction) -> None:
        """param_list_opt : param_list
                          | VOID
                          | empty"""
        if p[1] is None or p[1] == "void":
            p[0] = []
        else:
            p[0] = p[1]

    def p_param_list(self, p: yacc.YaccProduction) -> None:
        """param_list : param_list COMMA param
                      | param"""
        if len(p) == 4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]

    def p_param(self, p: yacc.YaccProduction) -> None:
        """param : type_spec ID
                 | type_spec ID LBRACKET RBRACKET
                 | CONST type_spec ID
                 | CONST type_spec ID LBRACKET RBRACKET"""
        if len(p) == 3:
            p[0] = Param(param_type=p[1], name=p[2], is_array=False, line=p.lineno(2))
        elif len(p) == 5 and p[1] != "const":
            p[0] = Param(param_type=p[1], name=p[2], is_array=True, line=p.lineno(2))
        elif len(p) == 4:
            p[0] = Param(param_type=p[2], name=p[3], is_array=False, line=p.lineno(3))
        else:
            p[0] = Param(param_type=p[2], name=p[3], is_array=True, line=p.lineno(3))

    def p_var_decl(self, p: yacc.YaccProduction) -> None:
        """var_decl : type_spec init_declarator_list SEMI
                    | CONST type_spec init_declarator_list SEMI"""
        if len(p) == 4:
            line = p[2][0].line if p[2] else p.lineno(3)
            p[0] = VarDecl(var_type=p[1], declarations=p[2], is_const=False, line=line)
        else:
            line = p[3][0].line if p[3] else p.lineno(1)
            p[0] = VarDecl(var_type=p[2], declarations=p[3], is_const=True, line=line)

    def p_init_declarator_list(self, p: yacc.YaccProduction) -> None:
        """init_declarator_list : init_declarator_list COMMA init_declarator
                                | init_declarator"""
        if len(p) == 4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]

    def p_init_declarator_scalar(self, p: yacc.YaccProduction) -> None:
        """init_declarator : ID
                           | ID ASSIGN expr"""
        init_val = p[3] if len(p) == 4 else None
        p[0] = VarInit(name=p[1], init=init_val, is_array=False, line=p.lineno(1))

    def p_init_declarator_array(self, p: yacc.YaccProduction) -> None:
        """init_declarator : ID LBRACKET expr RBRACKET
                           | ID LBRACKET expr RBRACKET ASSIGN LBRACE arg_list_opt RBRACE
                           | ID LBRACKET RBRACKET ASSIGN LBRACE arg_list_opt RBRACE"""
        if len(p) == 5:
            p[0] = VarInit(
                name=p[1],
                array_size=p[3],
                is_array=True,
                line=p.lineno(1),
            )
        elif len(p) == 9:
            p[0] = VarInit(
                name=p[1],
                array_size=p[3],
                init=ArrayInitializer(elements=p[7], line=p.lineno(6)),
                is_array=True,
                line=p.lineno(1),
            )
        else:
            p[0] = VarInit(
                name=p[1],
                array_size=None,
                init=ArrayInitializer(elements=p[6], line=p.lineno(5)),
                is_array=True,
                line=p.lineno(1),
            )

    def p_compound_stmt(self, p: yacc.YaccProduction) -> None:
        """compound_stmt : LBRACE block_item_list RBRACE"""
        p[0] = Block(statements=p[2], line=p.lineno(1))

    def p_block_item_list(self, p: yacc.YaccProduction) -> None:
        """block_item_list : block_item_list block_item
                           | empty"""
        if len(p) == 3:
            p[0] = p[1] + [p[2]]
        else:
            p[0] = []

    def p_block_item(self, p: yacc.YaccProduction) -> None:
        """block_item : var_decl
                      | stmt"""
        p[0] = p[1]

    def p_stmt(self, p: yacc.YaccProduction) -> None:
        """stmt : compound_stmt
                | expr_stmt
                | if_stmt
                | while_stmt
                | do_while_stmt
                | for_stmt
                | jump_stmt"""
        p[0] = p[1]

    def p_expr_stmt(self, p: yacc.YaccProduction) -> None:
        """expr_stmt : expr SEMI
                     | SEMI"""
        if len(p) == 3:
            p[0] = ExprStmt(expr=p[1], line=p[1].line)
        else:
            p[0] = EmptyStmt(line=p.lineno(1))

    def p_if_stmt(self, p: yacc.YaccProduction) -> None:
        """if_stmt : IF LPAREN expr RPAREN stmt %prec LOWER_THAN_ELSE
                   | IF LPAREN expr RPAREN stmt ELSE stmt"""
        if len(p) == 6:
            p[0] = IfStmt(condition=p[3], then_branch=p[5], else_branch=None, line=p.lineno(1))
        else:
            p[0] = IfStmt(condition=p[3], then_branch=p[5], else_branch=p[7], line=p.lineno(1))

    def p_while_stmt(self, p: yacc.YaccProduction) -> None:
        """while_stmt : WHILE LPAREN expr RPAREN stmt"""
        p[0] = WhileStmt(condition=p[3], body=p[5], line=p.lineno(1))

    def p_do_while_stmt(self, p: yacc.YaccProduction) -> None:
        """do_while_stmt : DO stmt WHILE LPAREN expr RPAREN SEMI"""
        p[0] = DoWhileStmt(body=p[2], condition=p[5], line=p.lineno(1))

    def p_for_stmt(self, p: yacc.YaccProduction) -> None:
        """for_stmt : FOR LPAREN var_decl expr_opt SEMI expr_opt RPAREN stmt
                    | FOR LPAREN expr_opt SEMI expr_opt SEMI expr_opt RPAREN stmt"""
        if len(p) == 9:
            p[0] = ForStmt(init=p[3], condition=p[4], update=p[6], body=p[8], line=p.lineno(1))
        else:
            p[0] = ForStmt(init=p[3], condition=p[5], update=p[7], body=p[9], line=p.lineno(1))

    def p_expr_opt(self, p: yacc.YaccProduction) -> None:
        """expr_opt : expr
                    | empty"""
        p[0] = p[1]

    def p_jump_stmt(self, p: yacc.YaccProduction) -> None:
        """jump_stmt : RETURN expr SEMI
                     | RETURN SEMI
                     | BREAK SEMI
                     | CONTINUE SEMI"""
        kw = p[1]
        if kw == "return":
            val = p[2] if len(p) == 4 else None
            p[0] = ReturnStmt(value=val, line=p.lineno(1))
        elif kw == "break":
            p[0] = BreakStmt(line=p.lineno(1))
        else:
            p[0] = ContinueStmt(line=p.lineno(1))

    def p_expr(self, p: yacc.YaccProduction) -> None:
        """expr : bin_expr
                | postfix_expr assign_op expr"""
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = Assignment(target=p[1], op=p[2], value=p[3], line=p[1].line)

    def p_assign_op(self, p: yacc.YaccProduction) -> None:
        """assign_op : ASSIGN
                     | PLUS_ASSIGN
                     | MINUS_ASSIGN
                     | MUL_ASSIGN
                     | DIV_ASSIGN
                     | MOD_ASSIGN"""
        p[0] = p[1]

    def p_bin_expr(self, p: yacc.YaccProduction) -> None:
        """bin_expr : unary_expr
                    | bin_expr PLUS bin_expr
                    | bin_expr MINUS bin_expr
                    | bin_expr TIMES bin_expr
                    | bin_expr DIVIDE bin_expr
                    | bin_expr MOD bin_expr
                    | bin_expr LT bin_expr
                    | bin_expr LE bin_expr
                    | bin_expr GT bin_expr
                    | bin_expr GE bin_expr
                    | bin_expr EQ bin_expr
                    | bin_expr NEQ bin_expr
                    | bin_expr AND bin_expr
                    | bin_expr OR bin_expr
                    | bin_expr BIT_AND bin_expr
                    | bin_expr BIT_OR bin_expr
                    | bin_expr BIT_XOR bin_expr
                    | bin_expr LSHIFT bin_expr
                    | bin_expr RSHIFT bin_expr"""
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = BinaryOp(op=p[2], left=p[1], right=p[3], line=p[1].line)

    def p_unary_expr(self, p: yacc.YaccProduction) -> None:
        """unary_expr : postfix_expr
                      | PLUS unary_expr
                      | MINUS unary_expr
                      | NOT unary_expr
                      | BIT_NOT unary_expr
                      | PLUS_PLUS unary_expr
                      | MINUS_MINUS unary_expr"""
        if len(p) == 2:
            p[0] = p[1]
        else:
            p[0] = UnaryOp(op=p[1], operand=p[2], prefix=True, line=p.lineno(1))

    def p_postfix_expr(self, p: yacc.YaccProduction) -> None:
        """postfix_expr : primary_expr
                        | postfix_expr LBRACKET expr RBRACKET
                        | postfix_expr PLUS_PLUS
                        | postfix_expr MINUS_MINUS"""
        if len(p) == 2:
            p[0] = p[1]
        elif len(p) == 5:
            p[0] = ArrayAccess(array=p[1], index=p[3], line=p[1].line)
        else:
            p[0] = UnaryOp(op=p[2], operand=p[1], prefix=False, line=p[1].line)

    def p_primary_expr_id_or_call(self, p: yacc.YaccProduction) -> None:
        """primary_expr : ID
                        | ID LPAREN arg_list_opt RPAREN"""
        if len(p) == 2:
            p[0] = Identifier(name=p[1], line=p.lineno(1))
        else:
            p[0] = FuncCall(name=p[1], args=p[3], line=p.lineno(1))

    def p_primary_expr_parens(self, p: yacc.YaccProduction) -> None:
        """primary_expr : LPAREN expr RPAREN"""
        p[0] = p[2]

    def p_primary_expr_literals(self, p: yacc.YaccProduction) -> None:
        """primary_expr : INT_LITERAL
                        | FLOAT_LITERAL
                        | CHAR_LITERAL
                        | STRING_LITERAL
                        | TRUE
                        | FALSE"""
        tok_type = p.slice[1].type
        val = p[1]
        line = p.lineno(1)
        if tok_type == "INT_LITERAL":
            p[0] = Literal(value=val, literal_type="int", line=line)
        elif tok_type == "FLOAT_LITERAL":
            p[0] = Literal(value=val, literal_type="float", line=line)
        elif tok_type == "CHAR_LITERAL":
            p[0] = Literal(value=val, literal_type="char", line=line)
        elif tok_type == "STRING_LITERAL":
            p[0] = Literal(value=val, literal_type="string", line=line)
        elif tok_type == "TRUE":
            p[0] = Literal(value=True, literal_type="bool", line=line)
        else:
            p[0] = Literal(value=False, literal_type="bool", line=line)

    def p_arg_list_opt(self, p: yacc.YaccProduction) -> None:
        """arg_list_opt : arg_list
                        | empty"""
        p[0] = p[1] if p[1] is not None else []

    def p_arg_list(self, p: yacc.YaccProduction) -> None:
        """arg_list : arg_list COMMA expr
                    | expr"""
        if len(p) == 4:
            p[0] = p[1] + [p[3]]
        else:
            p[0] = [p[1]]

    def p_empty(self, p: yacc.YaccProduction) -> None:
        """empty :"""
        p[0] = None

    def p_error(self, p: Any) -> None:
        if p is not None:
            col = find_column(self.source_code, p.lexpos)
            self.errors.append(
                ParseError(
                    message=f"Синтаксична помилка біля {p.value!r} (рядок {p.lineno}, стовпець {col})",
                    line=p.lineno,
                    column=col,
                )
            )
            while True:
                tok = self.parser.token()
                if not tok or tok.type in ("SEMI", "RBRACE"):
                    break
            self.parser.errok()
        else:
            lines = self.source_code.splitlines() or [""]
            self.errors.append(
                ParseError(
                    message="Неочікуваний кінець файлу (EOF)",
                    line=len(lines),
                    column=len(lines[-1]) + 1,
                )
            )

    def parse(self, source: str) -> tuple[Program | None, list[LexError], list[ParseError]]:
        self.source_code = source
        self.errors.clear()
        self.c_lexer.reset(source)
        ast_root = self.parser.parse(source, lexer=self.c_lexer.lexer)
        return ast_root, list(self.c_lexer.errors), list(self.errors)

    def get_lalr_stats(self) -> dict[str, Any]:
        stats: dict[str, Any] = {
            "method": "LALR(1)",
            "rulesCount": len(self.parser.productions) - 1,
            "statesCount": len(self.parser.action),
            "shiftReduceConflicts": 0,
            "reduceReduceConflicts": 0,
            "warnings": [],
            "sampleStates": [],
        }
        if self.debug_file.exists():
            text = self.debug_file.read_text(encoding="utf-8", errors="replace")
            sr_match = re.findall(r"(\d+)\s+shift/reduce conflict", text)
            rr_match = re.findall(r"(\d+)\s+reduce/reduce conflict", text)
            if sr_match:
                stats["shiftReduceConflicts"] = sum(int(x) for x in sr_match)
            if rr_match:
                stats["reduceReduceConflicts"] = sum(int(x) for x in rr_match)
            for line in text.splitlines():
                if "WARNING" in line or "conflict" in line.lower():
                    stats["warnings"].append(line.strip())
            state_blocks = re.split(r"\n(?=state \d+\n)", text)
            for block in state_blocks[1:26]:
                stats["sampleStates"].append(block.strip())
        return stats
