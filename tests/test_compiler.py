from __future__ import annotations
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
import urllib.request

from c_compiler.lexer import CLexer
from c_compiler.pipeline import CompilerPipeline
from c_compiler.presets import PRESETS
from server import CompilerRequestHandler


class TestCCompilerLab3(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pipeline = CompilerPipeline()

    def test_lalr_zero_conflicts(self) -> None:
        stats = self.pipeline.parser.get_lalr_stats()
        self.assertEqual(stats["shiftReduceConflicts"], 0)
        self.assertEqual(stats["reduceReduceConflicts"], 0)
        self.assertEqual(stats["warnings"], [])
        self.assertGreater(stats["statesCount"], 150)

    def test_lexer_tokens_and_comments(self) -> None:
        code = (
            "#include <stdio.h>\n"
            "int x = 0x10;\n"
            "float f = 3.5;\n"
        )
        lexer = CLexer()
        toks, errs = lexer.tokenize(code)
        self.assertEqual(errs, [])
        self.assertEqual(len(lexer.preprocessor_directives), 1)
        types = [t["type"] for t in toks]
        self.assertEqual(
            types,
            ["INT", "ID", "ASSIGN", "INT_LITERAL", "SEMI", "FLOAT", "ID", "ASSIGN", "FLOAT_LITERAL", "SEMI"],
        )
        self.assertEqual(toks[3]["value"], "16")

    def test_lexer_error_reporting(self) -> None:
        lexer = CLexer()
        _, errs = lexer.tokenize("int a = 5 @ 2;")
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].character, "@")

    def test_operator_precedence_and_dangling_else(self) -> None:
        code = """
        int main() {
            int r = 2 + 3 * 4;
            int out = 0;
            if (0)
                if (1)
                    out = 10;
                else
                    out = 20;
            printf("%d %d\\n", r, out);
            return 0;
        }
        """
        res = self.pipeline.process(code)
        self.assertTrue(res["success"])
        self.assertEqual(res["astExecution"]["stdout"], "14 0\n")
        self.assertEqual(res["pythonExecution"]["stdout"], "14 0\n")

    def test_all_valid_presets_match_python_translation(self) -> None:
        for preset in PRESETS[:5]:
            with self.subTest(preset=preset["id"]):
                res = self.pipeline.process(preset["code"])
                self.assertTrue(res["success"], f"Діагностика: {res['diagnostics']}")
                self.assertIsNotNone(res["astExecution"])
                self.assertIsNotNone(res["pythonExecution"])
                self.assertEqual(res["pythonExecution"]["exitCode"], 0, res["pythonExecution"]["stderr"])
                self.assertEqual(
                    res["astExecution"]["stdout"],
                    res["pythonExecution"]["stdout"],
                )

    def test_semantic_errors_detected(self) -> None:
        err_preset = PRESETS[5]
        res = self.pipeline.process(err_preset["code"])
        self.assertFalse(res["success"])
        self.assertGreaterEqual(len(res["diagnostics"]), 4)

    def test_global_var_mutation_and_for_continue(self) -> None:
        code = """
        int counter = 0;

        void bump(int limit) {
            for (int i = 0; i < limit; i++) {
                if (i % 2 == 1) {
                    continue;
                }
                counter += i;
            }
        }

        int main() {
            bump(6);
            printf("counter=%d\\n", counter);
            return 0;
        }
        """
        res = self.pipeline.process(code)
        self.assertTrue(res["success"])
        self.assertIn("global counter", res["pythonCode"])
        self.assertEqual(res["astExecution"]["stdout"], "counter=6\n")
        self.assertEqual(res["pythonExecution"]["stdout"], "counter=6\n")

    def test_web_server_api_and_static_assets(self) -> None:
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), CompilerRequestHandler)
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{port}"
            with urllib.request.urlopen(f"{base}/") as r:
                html = r.read().decode("utf-8")
                self.assertIn("d3.v7.min.js", html)

            with urllib.request.urlopen(f"{base}/vendor/d3.v7.min.js") as r:
                self.assertEqual(r.status, 200)
                self.assertGreater(len(r.read()), 100_000)

            req = urllib.request.Request(
                f"{base}/api/compile",
                data=json.dumps({"code": "int main() { printf(\"OK\\n\"); return 0; }"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as r:
                payload = json.loads(r.read().decode("utf-8"))
                self.assertTrue(payload["success"])
                self.assertEqual(payload["pythonExecution"]["stdout"], "OK\n")
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
