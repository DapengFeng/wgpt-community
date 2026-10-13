"""Verify that the public teaching demo remains local, synthetic and deterministic."""

import hashlib
import json
import re
import shutil
import subprocess
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demos"


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets = []
        self.policies = []
        self.inline_scripts = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and "src" not in attrs:
            self.inline_scripts += 1
        if "src" in attrs:
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append(attrs["href"])
        if tag == "meta" and attrs.get("http-equiv", "").lower() == "content-security-policy":
            self.policies.append(attrs["content"])


class DemoTests(unittest.TestCase):
    def test_page_loads_only_bundled_assets_and_blocks_connections(self):
        page = PageAssets()
        page.feed((DEMO / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(page.inline_scripts, 0)
        self.assertTrue(page.assets)
        for asset in page.assets:
            self.assertNotIn(":", asset)
            path = (DEMO / asset).resolve()
            self.assertTrue(path.is_relative_to(DEMO))
            self.assertTrue(path.is_file())
        self.assertEqual(len(page.policies), 1)
        directives = {part.strip() for part in page.policies[0].split(";")}
        for required in ("default-src 'none'", "connect-src 'none'", "object-src 'none'", "form-action 'none'"):
            self.assertIn(required, directives)

    def test_demo_has_no_network_or_dynamic_code_entry_points(self):
        script = (DEMO / "demo.js").read_text(encoding="utf-8")
        self.assertNotRegex(script, r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|Worker|eval|Function)\s*\(")
        self.assertNotRegex(script, r"https?://|\bimport\s*\(|\brequire\s*\(")
        self.assertNotIn("innerHTML", script)
        css = (DEMO / "style.css").read_text(encoding="utf-8")
        self.assertNotRegex(css, r"@import\b|url\s*\(")

    def test_shareable_art_is_original_static_svg_with_a_synthetic_label(self):
        svg = ET.parse(DEMO / "overview.svg").getroot()
        tags = {element.tag.rsplit("}", 1)[-1] for element in svg.iter()}
        self.assertFalse({"script", "image", "foreignObject", "use"} & tags)
        text = " ".join(svg.itertext())
        self.assertIn("OFFLINE", text)
        self.assertIn("SYNTHETIC", text)
        self.assertIn("非产品截图", text)

    def test_local_documentation_links_resolve(self):
        for document in [ROOT / "README.md", ROOT / "CONTRIBUTING.md", DEMO / "README.md"]:
            for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                if "://" in target or target.startswith("#"):
                    continue
                path = (document.parent / target.split("#", 1)[0]).resolve()
                self.assertTrue(path.is_relative_to(ROOT))
                self.assertTrue(path.exists(), f"Missing local link in {document.name}: {target}")

    def test_published_recordings_match_sources_and_remain_small_finite_gifs(self):
        manifest = json.loads((DEMO / "recordings/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        self.assertTrue(manifest["synthetic"])
        self.assertEqual(manifest["provider_calls"], 0)
        self.assertEqual(set(manifest["sources"]), {"index.html", "style.css", "demo.js"})
        for name, digest in manifest["sources"].items():
            self.assertEqual(hashlib.sha256((DEMO / name).read_bytes()).hexdigest(), digest, "Re-record changed demos")
        self.assertEqual(
            hashlib.sha256((ROOT / "scripts/record_demos.py").read_bytes()).hexdigest(),
            manifest["recorder_sha256"], "Re-record after changing capture settings",
        )
        self.assertEqual({item["file"] for item in manifest["recordings"]}, {"protocol.gif", "recovery.gif", "tools.gif"})
        for item in manifest["recordings"]:
            data = (DEMO / "recordings" / item["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), item["sha256"])
            self.assertEqual(data[:6], b"GIF89a")
            self.assertEqual(int.from_bytes(data[6:8], "little"), manifest["width"])
            self.assertEqual(int.from_bytes(data[8:10], "little"), manifest["height"])
            self.assertNotIn(b"NETSCAPE2.0", data, "Recordings should play once, not loop indefinitely")
            self.assertLess(len(data), 1_000_000, "Keep inline previews lightweight")

    def test_deterministic_scenarios_with_node(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Demo tests require Node.js 18 or newer on PATH")
        result = subprocess.run(
            [node, "--test-reporter=tap", str(ROOT / "tests" / "demo.test.cjs")],
            cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Verify registered cases actually ran, rather than only loading the file.
        counts = re.search(r"^# tests (\d+)$", result.stdout, re.MULTILINE)
        self.assertIsNotNone(counts, result.stdout)
        self.assertGreater(int(counts[1]), 0)


if __name__ == "__main__":
    unittest.main()
