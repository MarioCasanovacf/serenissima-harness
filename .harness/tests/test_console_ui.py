"""Static checks of the console page (design T-484 sections 7 and 8).

Every label the page uses exists in both languages; the page loads nothing from another
origin and carries no inline script or style (the server's CSP forbids both); no data is
ever written into the DOM as HTML; no emoji and no em dash in what the reader sees.
"""
import json
import pathlib
import re
import unittest

UI = pathlib.Path(__file__).resolve().parents[1] / "ui"
KEY_PREFIX = r"(?:app|tab|live|op|soc|flows|ev|st|board|git|time|tip|form|chart|common)"


def used_keys():
    js = (UI / "app.js").read_text(encoding="utf-8")
    html = (UI / "index.html").read_text(encoding="utf-8")
    keys = set(re.findall(r'"(' + KEY_PREFIX + r'\.[a-z0-9_.]+)"', js))
    keys |= set(re.findall(r'data-i18n(?:-placeholder)?="([^"]+)"', html))
    return keys


class TestLanguages(unittest.TestCase):
    def setUp(self):
        self.es = json.loads((UI / "i18n" / "es.json").read_text(encoding="utf-8"))
        self.en = json.loads((UI / "i18n" / "en.json").read_text(encoding="utf-8"))

    def test_both_languages_hold_the_same_keys(self):
        self.assertEqual(sorted(set(self.es) ^ set(self.en)), [])

    def test_every_key_the_page_uses_exists_in_both(self):
        keys = used_keys()
        self.assertGreater(len(keys), 100)
        self.assertEqual(sorted(keys - set(self.es)), [])
        self.assertEqual(sorted(keys - set(self.en)), [])

    def test_placeholders_match_between_languages(self):
        for k in self.es:
            self.assertEqual(sorted(re.findall(r"\{(\w+)\}", self.es[k])),
                             sorted(re.findall(r"\{(\w+)\}", self.en[k])), k)

    def test_no_emoji_and_no_em_dash(self):
        bad = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u2014]")
        for name in ("index.html", "app.js", "styles.css", "i18n/es.json", "i18n/en.json"):
            text = (UI / name).read_text(encoding="utf-8")
            self.assertIsNone(bad.search(text), name)


class TestNoOtherOrigin(unittest.TestCase):
    def test_index_loads_only_its_own_files(self):
        html = (UI / "index.html").read_text(encoding="utf-8")
        refs = re.findall(r'(?:src|href)="([^"]*)"', html)
        self.assertTrue(refs)
        for ref in refs:
            self.assertTrue(ref.startswith("/ui/"), ref)
        self.assertNotRegex(html, r"https?://|//[a-z]")

    def test_no_inline_script_or_style(self):
        html = (UI / "index.html").read_text(encoding="utf-8")
        self.assertEqual(re.findall(r"<script(?![^>]*\bsrc=)[^>]*>", html), [])
        self.assertNotIn("<style", html)
        self.assertNotRegex(html, r"\sstyle=")
        self.assertNotRegex(html, r"\son[a-z]+=")

    def test_scripts_and_styles_reach_no_other_origin(self):
        js = (UI / "app.js").read_text(encoding="utf-8")
        urls = set(re.findall(r"https?://[^\s\"')]+", js))
        self.assertEqual(urls, {"http://www.w3.org/2000/svg"})
        css = (UI / "styles.css").read_text(encoding="utf-8")
        self.assertNotIn("@import", css)
        self.assertNotRegex(css, r"url\(")

    def test_data_never_becomes_html(self):
        js = (UI / "app.js").read_text(encoding="utf-8")
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
            self.assertNotIn(sink, js)

    def test_writes_carry_the_token(self):
        js = (UI / "app.js").read_text(encoding="utf-8")
        self.assertIn('"X-Console-Token": TOKEN', js)
        # Exactly two network calls: get() never writes, send() always carries the token.
        self.assertEqual(len(re.findall(r"\bfetch\(", js)), 2)
        send = js[js.index("function send("):js.index("function reason(")]
        self.assertIn('"X-Console-Token": TOKEN', send)
        get = js[js.index("function get("):js.index("function send(")]
        self.assertNotIn("method", get)
        self.assertNotRegex(js, r"XMLHttpRequest|sendBeacon|new WebSocket")
        html = (UI / "index.html").read_text(encoding="utf-8")
        self.assertIn('content="__CONSOLE_TOKEN__"', html)


if __name__ == "__main__":
    unittest.main()
