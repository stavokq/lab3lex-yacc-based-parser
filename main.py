from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys

from c_compiler.pipeline import CompilerPipeline
from server import start_server


def _configure_utf8_console() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def _print_ast_ascii(node: dict, prefix: str = "", is_last: bool = True) -> None:
    connector = "└── " if is_last else "├── "
    type_suffix = f" [{node['inferredType']}]" if node.get("inferredType") else ""
    line_info = f" (ряд. {node['line']})" if node.get("line") else ""
    print(f"{prefix}{connector}{node['name']}{type_suffix}{line_info}")
    children = node.get("children", [])
    next_prefix = prefix + ("    " if is_last else "│   ")
    for idx, child in enumerate(children):
        _print_ast_ascii(child, next_prefix, idx == len(children) - 1)


def run_cli(args: argparse.Namespace) -> int:
    src_path = Path(args.file)
    if not src_path.exists():
        print(f"Помилка: файл '{src_path}' не знайдено.", file=sys.stderr)
        return 1

    source = src_path.read_text(encoding="utf-8")
    pipeline = CompilerPipeline()
    result = pipeline.process(source, run_ast=args.run, run_python=args.run)

    lalr = result["lalrStats"]
    print(f"Файл: {src_path} | Токенів: {len(result['tokens'])}")
    print(
        f"LALR(1): правил={lalr['rulesCount']}, станів={lalr['statesCount']}, "
        f"S/R={lalr['shiftReduceConflicts']}, R/R={lalr['reduceReduceConflicts']}"
    )

    if args.tokens:
        print("\nТокени:")
        for i, tok in enumerate(result["tokens"], 1):
            print(f"  {i:3d}. {tok['type']:<16} {tok['value']:<20} ({tok['line']}:{tok['column']})")

    if result["diagnostics"]:
        print("\nДіагностика:")
        for d in result["diagnostics"]:
            print(f"  [{d['type']}] рядок {d['line']}: {d['message']}")

    if not result["success"]:
        return 2

    if result["ast"] is not None:
        print(f"\nAST ({result['astNodeCount']} вузлів):")
        _print_ast_ascii(result["ast"])

    if args.ast_json:
        json_path = Path(args.ast_json)
        json_path.write_text(json.dumps(result["ast"], ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nAST JSON: {json_path}")

    print("\nКод Python:")
    print(result["pythonCode"])

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(result["pythonCode"], encoding="utf-8")
        print(f"Збережено: {out_path}")

    if args.run:
        if result["astExecution"]:
            ast_exec = result["astExecution"]
            print("Вивід AST:")
            if ast_exec["error"]:
                print(f"Помилка: {ast_exec['error']}")
            else:
                print(ast_exec["stdout"], end="" if ast_exec["stdout"].endswith("\n") else "\n")
                print(f"return={ast_exec['returnValue']}, steps={ast_exec['steps']}")
        if result["pythonExecution"]:
            py_exec = result["pythonExecution"]
            print("\nВивід Python:")
            print(py_exec["stdout"], end="" if py_exec["stdout"].endswith("\n") else "\n")
            if py_exec["stderr"]:
                print(py_exec["stderr"], file=sys.stderr)

    return 0


def main() -> None:
    _configure_utf8_console()
    parser = argparse.ArgumentParser(description="Синтаксичний аналізатор C (PLY)")
    parser.add_argument("file", nargs="?", help="Вхідний файл .c")
    parser.add_argument("-o", "--output", help="Вихідний файл .py")
    parser.add_argument("--ast-json", help="Зберегти AST у JSON")
    parser.add_argument("--tokens", action="store_true", help="Вивести токени")
    parser.add_argument("--run", action="store_true", help="Виконати AST та Python-код")
    parser.add_argument("--host", default="127.0.0.1", help="Хост сервера")
    parser.add_argument("--port", type=int, default=8000, help="Порт сервера")
    parser.add_argument("--no-browser", action="store_true", help="Без автозапуску браузера")

    args = parser.parse_args()
    if args.file:
        sys.exit(run_cli(args))
    else:
        start_server(host=args.host, port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
