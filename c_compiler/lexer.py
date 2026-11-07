from __future__ import annotations
from dataclasses import dataclass
from typing import Any
import ply.lex as lex


RESERVED: dict[str, str] = {
    "int": "INT",
    "float": "FLOAT",
    "double": "DOUBLE",
    "char": "CHAR",
    "void": "VOID",
    "bool": "BOOL",
    "const": "CONST",
    "if": "IF",
    "else": "ELSE",
    "while": "WHILE",
    "for": "FOR",
    "do": "DO",
    "return": "RETURN",
    "break": "BREAK",
    "continue": "CONTINUE",
    "true": "TRUE",
    "false": "FALSE",
}

tokens: tuple[str, ...] = (
    "ID",
    "INT_LITERAL",
    "FLOAT_LITERAL",
    "CHAR_LITERAL",
    "STRING_LITERAL",
    "PLUS",
    "MINUS",
    "TIMES",
    "DIVIDE",
    "MOD",
    "PLUS_PLUS",
    "MINUS_MINUS",
    "ASSIGN",
    "PLUS_ASSIGN",
    "MINUS_ASSIGN",
    "MUL_ASSIGN",
    "DIV_ASSIGN",
    "MOD_ASSIGN",
    "EQ",
    "NEQ",
    "LT",
    "LE",
    "GT",
    "GE",
    "AND",
    "OR",
    "NOT",
    "BIT_AND",
    "BIT_OR",
    "BIT_XOR",
    "BIT_NOT",
    "LSHIFT",
    "RSHIFT",
    "LPAREN",
    "RPAREN",
    "LBRACE",
    "RBRACE",
    "LBRACKET",
    "RBRACKET",
    "SEMI",
    "COMMA",
) + tuple(RESERVED.values())


@dataclass
class LexError:
    message: str
    line: int
    column: int
    character: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "LexicalError",
            "message": self.message,
            "line": self.line,
            "column": self.column,
        }


def find_column(source: str, lexpos: int) -> int:
    line_start = source.rfind("\n", 0, lexpos) + 1
    return (lexpos - line_start) + 1


def _unescape_c_string(raw: str) -> str:
    escapes = {
        "n": "\n",
        "t": "\t",
        "r": "\r",
        "0": "\0",
        "\\": "\\",
        '"': '"',
        "'": "'",
    }
    result: list[str] = []
    i = 0
    while i < len(raw):
        if raw[i] == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            result.append(escapes.get(nxt, nxt))
            i += 2
        else:
            result.append(raw[i])
            i += 1
    return "".join(result)


class CLexer:
    tokens = tokens

    t_PLUS_PLUS = r"\+\+"
    t_MINUS_MINUS = r"--"
    t_PLUS_ASSIGN = r"\+="
    t_MINUS_ASSIGN = r"-="
    t_MUL_ASSIGN = r"\*="
    t_DIV_ASSIGN = r"/="
    t_MOD_ASSIGN = r"%="

    t_EQ = r"=="
    t_NEQ = r"!="
    t_LE = r"<="
    t_GE = r">="
    t_LSHIFT = r"<<"
    t_RSHIFT = r">>"

    t_AND = r"&&"
    t_OR = r"\|\|"
    t_NOT = r"!"

    t_PLUS = r"\+"
    t_MINUS = r"-"
    t_TIMES = r"\*"
    t_DIVIDE = r"/"
    t_MOD = r"%"
    t_ASSIGN = r"="

    t_LT = r"<"
    t_GT = r">"

    t_BIT_AND = r"&"
    t_BIT_OR = r"\|"
    t_BIT_XOR = r"\^"
    t_BIT_NOT = r"~"

    t_LPAREN = r"\("
    t_RPAREN = r"\)"
    t_LBRACE = r"\{"
    t_RBRACE = r"\}"
    t_LBRACKET = r"\["
    t_RBRACKET = r"\]"
    t_SEMI = r";"
    t_COMMA = r","

    t_ignore = " \t\r"

    def __init__(self) -> None:
        self.errors: list[LexError] = []
        self.preprocessor_directives: list[dict[str, Any]] = []
        self.source_code: str = ""
        self.lexer = lex.lex(module=self)

    def t_COMMENT_MULTI(self, t: lex.LexToken) -> None:
        r"/\*(.|\n)*?\*/"
        t.lexer.lineno += t.value.count("\n")

    def t_COMMENT_SINGLE(self, t: lex.LexToken) -> None:
        r"//[^\n]*"
        pass

    def t_PREPROCESSOR(self, t: lex.LexToken) -> None:
        r"\#[^\n]*"
        self.preprocessor_directives.append(
            {"directive": t.value.strip(), "line": t.lexer.lineno}
        )

    def t_FLOAT_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r"((\d+\.\d*|\.\d+)([eE][+-]?\d+)?|\d+[eE][+-]?\d+)[fF]?"
        clean = t.value.rstrip("fF")
        t.value = float(clean)
        return t

    def t_INT_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r"0[xX][0-9a-fA-F]+|\d+"
        if t.value.lower().startswith("0x"):
            t.value = int(t.value, 16)
        else:
            t.value = int(t.value, 10)
        return t

    def t_CHAR_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r"'(\\.|[^\\'\n])'"
        t.value = _unescape_c_string(t.value[1:-1])
        return t

    def t_STRING_LITERAL(self, t: lex.LexToken) -> lex.LexToken:
        r'"(\\.|[^\\"\n])*"'
        t.value = _unescape_c_string(t.value[1:-1])
        return t

    def t_ID(self, t: lex.LexToken) -> lex.LexToken:
        r"[A-Za-z_][A-Za-z0-9_]*"
        t.type = RESERVED.get(t.value, "ID")
        return t

    def t_newline(self, t: lex.LexToken) -> None:
        r"\n+"
        t.lexer.lineno += len(t.value)

    def t_error(self, t: lex.LexToken) -> None:
        col = find_column(self.source_code, t.lexpos)
        bad_char = t.value[0]
        self.errors.append(
            LexError(
                message=f"Недопустимий символ {bad_char!r} у рядку {t.lexer.lineno}, стовпець {col}",
                line=t.lexer.lineno,
                column=col,
                character=bad_char,
            )
        )
        t.lexer.skip(1)

    def reset(self, source: str) -> None:
        self.source_code = source
        self.errors.clear()
        self.preprocessor_directives.clear()
        self.lexer.lineno = 1

    def tokenize(self, source: str) -> tuple[list[dict[str, Any]], list[LexError]]:
        self.reset(source)
        self.lexer.input(source)
        result: list[dict[str, Any]] = []
        while True:
            tok = self.lexer.token()
            if not tok:
                break
            result.append(
                {
                    "type": tok.type,
                    "value": repr(tok.value)
                    if isinstance(tok.value, str) and tok.type in ("STRING_LITERAL", "CHAR_LITERAL")
                    else str(tok.value),
                    "line": tok.lineno,
                    "column": find_column(source, tok.lexpos),
                }
            )
        return result, list(self.errors)
