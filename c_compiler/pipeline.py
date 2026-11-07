from __future__ import annotations
from typing import Any

from .codegen import PythonCodeGenerator, run_generated_python
from .interpreter import ASTInterpreter
from .lexer import CLexer
from .parser import CParser
from .semantics import SemanticAnalyzer


class CompilerPipeline:
    def __init__(self) -> None:
        self.lexer = CLexer()
        self.parser = CParser()
        self.semantics = SemanticAnalyzer()
        self.codegen = PythonCodeGenerator()

    def process(
        self,
        source_code: str,
        run_ast: bool = True,
        run_python: bool = True,
    ) -> dict[str, Any]:
        token_list, _ = self.lexer.tokenize(source_code)
        directives = list(self.lexer.preprocessor_directives)

        ast_root, lex_errors, parse_errors = self.parser.parse(source_code)
        diagnostics: list[dict[str, Any]] = [e.to_dict() for e in lex_errors] + [
            e.to_dict() for e in parse_errors
        ]

        has_syntax_errors = bool(lex_errors or parse_errors or ast_root is None)
        symbols_dict: list[dict[str, Any]] = []
        ast_dict: dict[str, Any] | None = None
        ast_node_count = 0
        python_code = ""
        ast_execution: dict[str, Any] | None = None
        python_execution: dict[str, Any] | None = None

        if not has_syntax_errors and ast_root is not None:
            symbols, sem_issues = self.semantics.analyze(ast_root)
            symbols_dict = [s.to_dict() for s in symbols]
            diagnostics.extend(issue.to_dict() for issue in sem_issues)

            ast_dict = ast_root.to_dict()
            ast_node_count = ast_root.count_nodes()

            has_sem_errors = any(issue.severity == "error" for issue in sem_issues)
            if not has_sem_errors:
                python_code = self.codegen.generate(ast_root)

                if run_ast:
                    interpreter = ASTInterpreter()
                    ast_execution = interpreter.execute(ast_root).to_dict()

                if run_python and python_code.strip():
                    python_execution = run_generated_python(python_code)

        return {
            "success": not any(
                d["type"] in ("LexicalError", "SyntaxError", "SemanticError")
                for d in diagnostics
            ),
            "tokens": token_list,
            "preprocessor": directives,
            "diagnostics": diagnostics,
            "symbols": symbols_dict,
            "ast": ast_dict,
            "astNodeCount": ast_node_count,
            "pythonCode": python_code,
            "astExecution": ast_execution,
            "pythonExecution": python_execution,
            "lalrStats": self.parser.get_lalr_stats(),
        }
