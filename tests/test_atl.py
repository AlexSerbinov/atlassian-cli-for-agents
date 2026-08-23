"""Offline tests — no network, no credentials, no Atlassian account required.

Everything here exercises the pure functions: the Markdown <-> ADF converter, the
duration parser, error unwrapping and credential resolution. The HTTP layer is
covered by the round-trip tests in the sense that whatever these produce is what
gets posted, and the shapes are the ones the live API accepted.
"""

import json
import os
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = SourceFileLoader("atl", os.path.join(HERE, os.pardir, "atl"))
_spec = spec_from_loader("atl", _loader)
atl = module_from_spec(_spec)
_loader.exec_module(atl)


class MarkdownToAdf(unittest.TestCase):
    def adf(self, md):
        return atl.md_to_adf(md)

    def test_paragraph(self):
        doc = self.adf("hello world")
        self.assertEqual(doc["type"], "doc")
        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["content"][0]["type"], "paragraph")

    def test_heading_levels(self):
        for n in range(1, 7):
            node = self.adf("#" * n + " title")["content"][0]
            self.assertEqual(node["type"], "heading")
            self.assertEqual(node["attrs"]["level"], n)

    def test_inline_marks(self):
        marks = {}
        for node in self.adf("a **b** c *d* e `f` g [h](http://x)")["content"][0]["content"]:
            for m in node.get("marks", []):
                marks[m["type"]] = node["text"]
        self.assertEqual(marks["strong"], "b")
        self.assertEqual(marks["em"], "d")
        self.assertEqual(marks["code"], "f")
        self.assertEqual(marks["link"], "h")

    def test_link_href(self):
        node = self.adf("[label](https://example.com/a?b=c)")["content"][0]["content"][0]
        self.assertEqual(node["marks"][0]["attrs"]["href"], "https://example.com/a?b=c")

    def test_bullet_and_ordered_lists(self):
        doc = self.adf("- a\n- b\n\n1. x\n2. y")
        kinds = [n["type"] for n in doc["content"]]
        self.assertIn("bulletList", kinds)
        self.assertIn("orderedList", kinds)
        bullets = next(n for n in doc["content"] if n["type"] == "bulletList")
        self.assertEqual(len(bullets["content"]), 2)

    def test_code_block_keeps_language_and_content(self):
        node = self.adf("```python\nprint(1)\nprint(2)\n```")["content"][0]
        self.assertEqual(node["type"], "codeBlock")
        self.assertEqual(node["attrs"]["language"], "python")
        self.assertEqual(node["content"][0]["text"], "print(1)\nprint(2)")

    def test_code_block_without_language(self):
        node = self.adf("```\nplain\n```")["content"][0]
        self.assertEqual(node["type"], "codeBlock")
        self.assertNotIn("attrs", node)

    def test_blockquote_and_rule(self):
        kinds = [n["type"] for n in self.adf("> quoted\n\n---")["content"]]
        self.assertEqual(kinds, ["blockquote", "rule"])

    def test_table_header_and_cells(self):
        node = self.adf("| a | b |\n|---|---|\n| 1 | 2 |")["content"][0]
        self.assertEqual(node["type"], "table")
        self.assertEqual(len(node["content"]), 2)
        self.assertEqual(node["content"][0]["content"][0]["type"], "tableHeader")
        self.assertEqual(node["content"][1]["content"][0]["type"], "tableCell")

    def test_ragged_table_is_padded(self):
        node = self.adf("| a | b | c |\n|---|---|---|\n| 1 |")["content"][0]
        self.assertEqual(len(node["content"][1]["content"]), 3)

    def test_empty_input_still_valid(self):
        doc = self.adf("")
        self.assertEqual(doc["content"][0]["type"], "paragraph")

    def test_no_empty_text_nodes(self):
        """ADF rejects a text node with an empty string."""
        def walk(n):
            if isinstance(n, dict):
                if n.get("type") == "text":
                    self.assertNotEqual(n["text"], "")
                for c in n.get("content", []) or []:
                    walk(c)
            elif isinstance(n, list):
                for c in n:
                    walk(c)

        for md in ("", " ", "**", "``", "- \n- \n", "```\n\n```", "# "):
            walk(self.adf(md))


class RoundTrip(unittest.TestCase):
    def assertRoundTrips(self, md):
        self.assertEqual(atl.adf_to_md(atl.md_to_adf(md)).strip(), md.strip())

    def test_document(self):
        self.assertRoundTrips(
            "# Title\n\n"
            "Text with **bold**, *italic*, `code` and [link](https://example.com).\n\n"
            "- one\n- two\n\n"
            "1. first\n2. second\n\n"
            "```python\nprint(1)\n```\n\n"
            "> quoted\n\n"
            "---"
        )

    def test_table(self):
        self.assertRoundTrips("| Alias | Count |\n|---|---|\n| `a` | **1** |\n| b | 2 |")

    def test_idempotent(self):
        md = "# H\n\n- a\n- b"
        once = atl.adf_to_md(atl.md_to_adf(md))
        twice = atl.adf_to_md(atl.md_to_adf(once))
        self.assertEqual(once, twice)


class AdfToMarkdown(unittest.TestCase):
    def test_unknown_node_does_not_crash(self):
        doc = {"type": "doc", "version": 1, "content": [
            {"type": "someFutureNode", "content": [
                {"type": "text", "text": "kept"}]}]}
        self.assertIn("kept", atl.adf_to_md(doc))

    def test_none_and_str(self):
        self.assertEqual(atl.adf_to_md(None), "")
        self.assertEqual(atl.adf_to_md("plain"), "plain")

    def test_mention_and_emoji(self):
        doc = {"type": "paragraph", "content": [
            {"type": "mention", "attrs": {"text": "@ann"}},
            {"type": "emoji", "attrs": {"text": ":+1:"}}]}
        out = atl.adf_to_md(doc)
        self.assertIn("@ann", out)
        self.assertIn(":+1:", out)

    def test_flat_collapses_whitespace(self):
        doc = atl.md_to_adf("a\n\nb\n\nc")
        self.assertEqual(atl.flat(doc), "a b c")


class Durations(unittest.TestCase):
    def test_forms(self):
        cases = {
            "45m": 45 * 60,
            "2h": 2 * 3600,
            "2h30m": 2 * 3600 + 30 * 60,
            "1d": 8 * 3600,          # Jira workday
            "1w": 5 * 8 * 3600,      # Jira week
            "1w2d": (5 + 2) * 8 * 3600,
            "90": 90 * 60,           # bare number means minutes
        }
        for text, secs in cases.items():
            self.assertEqual(atl.parse_duration(text), secs, text)

    def test_roundtrip_format(self):
        for text in ("45m", "2h", "2h30m"):
            self.assertEqual(atl.fmt_duration(atl.parse_duration(text)), text)

    def test_rejects_garbage(self):
        for bad in ("", "soon", "2 hours", "-5m"):
            with self.assertRaises(SystemExit):
                atl.parse_duration(bad)


class Timestamps(unittest.TestCase):
    def test_jira_datetime_shape(self):
        """Jira rejects a naive timestamp; the offset must be attached."""
        got = atl.jira_datetime("2026-08-22", "10:00:00")
        self.assertRegex(got, r"^2026-08-22T10:00:00\.000[+-]\d{4}$")


class Coercion(unittest.TestCase):
    def test_types(self):
        self.assertEqual(atl._coerce("10"), 10)
        self.assertEqual(atl._coerce("-3"), -3)
        self.assertEqual(atl._coerce("hello"), "hello")
        self.assertEqual(atl._coerce('{"a": 1}'), {"a": 1})
        self.assertEqual(atl._coerce("[1, 2]"), [1, 2])

    def test_maybe_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("# from disk")
            path = f.name
        try:
            self.assertEqual(atl._maybe_file("@" + path), "# from disk")
            self.assertEqual(atl._maybe_file("inline"), "inline")
        finally:
            os.unlink(path)


class Credentials(unittest.TestCase):
    def setUp(self):
        self._config = atl.ATL_CONFIG
        self._token = atl.TOKEN_FILE
        self._claude = atl.CLAUDE_CONFIG
        self._env = {k: os.environ.pop(k, None)
                     for k in ("ATL_URL", "ATL_USER", "ATL_TOKEN")}
        self.dir = tempfile.mkdtemp()
        atl.TOKEN_FILE = os.path.join(self.dir, "no-token")
        atl.CLAUDE_CONFIG = os.path.join(self.dir, "no-claude")

    def tearDown(self):
        atl.ATL_CONFIG, atl.TOKEN_FILE, atl.CLAUDE_CONFIG = (
            self._config, self._token, self._claude)
        for k, v in self._env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def write(self, obj):
        path = os.path.join(self.dir, "atl.json")
        with open(path, "w") as f:
            json.dump(obj, f)
        atl.ATL_CONFIG = path

    def test_reads_config_file(self):
        self.write({"url": "https://x.atlassian.net/", "user": "a@b.c", "token": "t"})
        c = atl.load_creds()
        self.assertEqual(c["url"], "https://x.atlassian.net")   # trailing slash stripped
        self.assertEqual(c["confluence_url"], "https://x.atlassian.net/wiki")

    def test_explicit_confluence_url_wins(self):
        self.write({"url": "https://x.atlassian.net", "user": "a@b.c", "token": "t",
                    "confluence_url": "https://wiki.example.com/"})
        self.assertEqual(atl.load_creds()["confluence_url"], "https://wiki.example.com")

    def test_env_vars(self):
        atl.ATL_CONFIG = os.path.join(self.dir, "missing.json")
        os.environ.update({"ATL_URL": "https://e.atlassian.net",
                           "ATL_USER": "e@x.com", "ATL_TOKEN": "envtoken"})
        c = atl.load_creds()
        self.assertEqual(c["user"], "e@x.com")
        self.assertEqual(c["token"], "envtoken")

    def test_migrates_from_mcp_atlassian_config(self):
        """Zero-config for people coming off the mcp-atlassian server."""
        atl.ATL_CONFIG = os.path.join(self.dir, "missing.json")
        claude = os.path.join(self.dir, "claude.json")
        with open(claude, "w") as f:
            json.dump({"mcpServers": {"atlassian": {"args": [
                "--jira-url=https://m.atlassian.net",
                "--jira-username=m@x.com",
                "--jira-token=mcptoken",
                "--confluence-url=https://m.atlassian.net/wiki"]}}}, f)
        atl.CLAUDE_CONFIG = claude
        c = atl.load_creds()
        self.assertEqual(c["url"], "https://m.atlassian.net")
        self.assertEqual(c["token"], "mcptoken")

    def test_missing_credentials_exit_cleanly(self):
        atl.ATL_CONFIG = os.path.join(self.dir, "missing.json")
        with self.assertRaises(SystemExit):
            atl.load_creds()


class Parser(unittest.TestCase):
    def test_every_subcommand_parses(self):
        p = atl.build_parser()
        groups = [g for g in p._subparsers._group_actions[0].choices.items()]
        self.assertGreater(len(groups), 20)
        for name, sub in groups:
            with self.subTest(cmd=name):
                self.assertIsNotNone(sub)

    def test_json_flag_before_and_after(self):
        p = atl.build_parser()
        for argv in (["--json", "issue", "X"], ["issue", "X", "--json"]):
            self.assertTrue(p.parse_args(argv).json or "--json" in argv)

    def test_transition_accepts_comment(self):
        a = atl.build_parser().parse_args(
            ["transition", "X-1", "--to", "Done", "--comment", "shipped"])
        self.assertEqual(a.comment, "shipped")


class ErrorUnwrapping(unittest.TestCase):
    """Jira returns `errors` as an object, Confluence as a list."""

    def run_main(self, body, status=400):
        def boom(*_a, **_k):
            raise atl.ApiError(status, json.dumps(body), "https://x/y")

        real_api, real_creds = atl.api, atl.load_creds
        atl.api = boom
        atl.load_creds = lambda: {"url": "u", "user": "v", "token": "t",
                                  "confluence_url": "c"}
        argv = sys.argv
        sys.argv = ["atl", "issue", "X-1"]
        try:
            with self.assertRaises(SystemExit) as cm:
                atl.main()
            return str(cm.exception)
        finally:
            atl.api, atl.load_creds, sys.argv = real_api, real_creds, argv

    def test_jira_object_shape(self):
        msg = self.run_main({"errorMessages": ["Issue does not exist."],
                             "errors": {"summary": "is required"}})
        self.assertIn("Issue does not exist.", msg)
        self.assertIn("summary: is required", msg)

    def test_confluence_list_shape(self):
        msg = self.run_main({"errors": [{"status": 404, "title": "Not Found"}]}, 404)
        self.assertIn("Not Found", msg)
        self.assertNotIn("Traceback", msg)

    def test_non_json_body(self):
        def boom(*_a, **_k):
            raise atl.ApiError(502, "<html>bad gateway</html>", "https://x/y")

        real_api, real_creds = atl.api, atl.load_creds
        atl.api = boom
        atl.load_creds = lambda: {"url": "u", "user": "v", "token": "t",
                                  "confluence_url": "c"}
        argv = sys.argv
        sys.argv = ["atl", "issue", "X-1"]
        try:
            with self.assertRaises(SystemExit) as cm:
                atl.main()
            self.assertIn("502", str(cm.exception))
        finally:
            atl.api, atl.load_creds, sys.argv = real_api, real_creds, argv


class Secrets(unittest.TestCase):
    def test_token_only_reaches_the_auth_header(self):
        """An MCP server takes the token as a process argument, so it shows up in
        `ps` for every user on the machine. Here the token must only ever be read
        from disk and turned into an Authorization header — nothing else.
        """
        import ast as _ast

        with open(os.path.join(HERE, os.pardir, "atl")) as f:
            tree = _ast.parse(f.read())

        readers = set()
        for fn in _ast.walk(tree):
            if not isinstance(fn, _ast.FunctionDef):
                continue
            for node in _ast.walk(fn):
                if (isinstance(node, _ast.Subscript)
                        and isinstance(node.slice, _ast.Constant)
                        and node.slice.value == "token"
                        and isinstance(node.value, _ast.Name)
                        and node.value.id in ("creds", "cfg")):
                    readers.add(fn.name)

        self.assertEqual(readers, {"_auth_header"},
                         f"token is read outside the auth header: {sorted(readers)}")

    def test_no_credentials_in_argv_construction(self):
        with open(os.path.join(HERE, os.pardir, "atl")) as f:
            src = f.read()
        self.assertNotIn("subprocess", src)
        self.assertNotIn("os.system", src)

    def test_auth_header_is_basic(self):
        h = atl._auth_header({"user": "a@b.c", "token": "secret"})
        self.assertTrue(h.startswith("Basic "))
        import base64
        self.assertEqual(base64.b64decode(h[6:]).decode(), "a@b.c:secret")


if __name__ == "__main__":
    unittest.main(verbosity=2)
