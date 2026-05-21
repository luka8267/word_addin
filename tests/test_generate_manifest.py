import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


BUNKEN_ROOT = Path(__file__).resolve().parents[1] / "bunkenn"
if str(BUNKEN_ROOT) not in sys.path:
    sys.path.insert(0, str(BUNKEN_ROOT))

import generate_manifest


class GenerateManifestTests(unittest.TestCase):
    def test_local_full_manifest_points_to_localhost(self):
        manifest = generate_manifest.render_manifest(
            generate_manifest.FULL_MANIFEST,
            base_url="http://localhost:4280",
            addin_id="A8C349E2-742D-499D-A5CF-0CDDF6CE5CD1",
        )

        root = ET.fromstring(manifest)

        self.assertTrue(root.tag.endswith("OfficeApp"))
        self.assertIn("http://localhost:4280/taskpane.html", manifest)
        self.assertNotIn("word-addin-sooty.vercel.app", manifest)

    def test_local_taskpane_manifest_has_no_version_overrides(self):
        manifest = generate_manifest.render_manifest(
            generate_manifest.TASKPANE_MANIFEST,
            base_url="https://localhost:4280",
            addin_id="E4FCB5D8-6D12-4B7C-A4E5-471628B020E6",
        )

        ET.fromstring(manifest)

        self.assertIn("https://localhost:4280/taskpane.html", manifest)
        self.assertNotIn("VersionOverrides", manifest)

    def test_local_base_url_is_restricted_to_loopback(self):
        generate_manifest.require_local_base_url("http://localhost:4280")
        generate_manifest.require_local_base_url("https://127.0.0.1:4280")

        with self.assertRaises(SystemExit):
            generate_manifest.require_local_base_url("http://example.com")

    def test_public_base_url_requires_https(self):
        generate_manifest.require_https_base_url("https://example.test")

        with self.assertRaises(SystemExit):
            generate_manifest.require_https_base_url("http://example.test")


if __name__ == "__main__":
    unittest.main()
