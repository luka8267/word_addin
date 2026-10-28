import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bunkenn/word-app/api"))

from shared.bunken_models import PaperSummary
from shared.bunken_service import (
    ADDITIONAL_STYLES, build_in_text_citation, build_bibliography_entry,
    get_csl_style_path, normalize_style,
)
from shared.custom_styles import format_custom, validate_custom_style
from api import _bunken_vercel as api


PAPER = PaperSummary("p1", "Example title", "Alice Alpha, Bob Beta", "Journal", 2024,
                     doi="https://doi.org/10.1234/test", volume="12", issue="3", pages="45-67")
CUSTOM = {
    "name": "研究室", "kind": "author-date", "superscript": False,
    "citationTemplate": "{author}（{year}）[[, {locator}]]",
    "bibliographyTemplate": "{authors}. {title}.[[ {journal}]][[ doi: {doi}]]",
}
NUMERIC = dict(CUSTOM, kind="numeric", superscript=True,
               citationTemplate="[{number}][[, {locator}]]",
               bibliographyTemplate="{number}) {title}[[ {doiUrl}]]")


class Handler:
    def __init__(self, payload):
        self.payload = payload

    def request_parts(self):
        return api.VercelRequest({}, {}, self.payload)

    def json_response(self, result, status=200):
        self.result, self.status = result, status


class CitationStyleTests(unittest.TestCase):
    def test_added_styles_use_installed_csl(self):
        for style in ADDITIONAL_STYLES:
            with self.subTest(style=style):
                self.assertIsNotNone(get_csl_style_path(style))
                text = build_bibliography_entry(PAPER, style)
                self.assertIn("example title", text.lower())
                self.assertIn("2024", text)
                self.assertIn("10.1234/test", text)

    def test_mla_and_harvard_have_distinct_in_text_citations(self):
        mla = build_in_text_citation(PAPER, "modern-language-association", "p. 25")
        harvard = build_in_text_citation(PAPER, "harvard-cite-them-right", "p. 25")
        self.assertNotIn("2024", mla)
        self.assertIn("25", mla)
        self.assertIn("2024", harvard)
        self.assertIn("p. 25", harvard)
        self.assertNotIn("p. p.", harvard)

    def test_invalid_style_does_not_silently_change_to_vancouver(self):
        self.assertEqual(normalize_style("APA.csl"), "apa")
        with self.assertRaises(ValueError):
            normalize_style("unknown-style-123")
        self.assertIsNone(get_csl_style_path("../apa"))

    def test_custom_text_and_missing_optional_fields(self):
        self.assertEqual(format_custom(PAPER, CUSTOM, "citationTemplate"), "Alice Alpha & Bob Beta（2024）")
        self.assertEqual(format_custom(PAPER, NUMERIC, "citationTemplate", 4, "p. 25"), "[4], p. 25")
        sparse = PaperSummary("p2", "日本語の文献", "", "", None)
        self.assertEqual(format_custom(sparse, CUSTOM, "bibliographyTemplate"), "Unknown. 日本語の文献.")
        self.assertIn("n.d.", format_custom(sparse, CUSTOM, "citationTemplate"))
        self.assertEqual(format_custom(PAPER, NUMERIC, "bibliographyTemplate", 2),
                         "2) Example title https://doi.org/10.1234/test")

    def test_templates_are_plain_text_not_recursive_code(self):
        paper = PaperSummary("p", "{year} <script>alert(1)</script>", "A", "", 2024)
        text = format_custom(paper, dict(CUSTOM, bibliographyTemplate="{title}"), "bibliographyTemplate")
        self.assertEqual(text, paper.title)

    def test_validation_rejects_invalid_definitions(self):
        for definition in [None, {}, dict(CUSTOM, name=""), dict(CUSTOM, name="a" * 81),
                           dict(CUSTOM, citationTemplate="{unknown}"),
                           dict(CUSTOM, citationTemplate="{title.__class__}"),
                           dict(CUSTOM, citationTemplate="{title"),
                           dict(CUSTOM, citationTemplate="[[{title}]"),
                           dict(CUSTOM, citationTemplate="[[[[{title}]]]]"),
                           dict(CUSTOM, citationTemplate="a" * 2001),
                           dict(CUSTOM, kind="numeric"),
                           dict(CUSTOM, superscript="true"),
                           dict(CUSTOM, citationTemplate="{number}")]:
            with self.subTest(definition=definition), self.assertRaises(ValueError):
                validate_custom_style(definition)
        with self.assertRaises(ValueError):
            format_custom(PAPER, NUMERIC, "citationTemplate")

    def test_preview_and_format_endpoints_share_custom_renderer(self):
        preview = Handler({"customStyle": NUMERIC})
        api.handle_styles_preview(preview)
        self.assertEqual(preview.result["citation"], "[1], p. 25")
        self.assertTrue(preview.result["superscript"])
        with patch.object(api, "resolve_request_context", return_value={}), patch.object(
            api, "fetch_papers_by_ids", return_value=[PAPER]
        ):
            citation = Handler({"style": "custom-lab", "customStyle": NUMERIC,
                                "items": [{"paperId": "p1", "referenceNumber": 5, "locator": "p. 25"}]})
            api.handle_citations_format(citation)
            self.assertEqual(citation.result["text"], "[5], p. 25")
            bibliography = Handler({"style": "custom-lab", "customStyle": NUMERIC, "paperIds": ["p1"]})
            api.handle_bibliography_format(bibliography)
            self.assertEqual(bibliography.result["entries"], ["1) Example title https://doi.org/10.1234/test"])

    def test_custom_id_requires_definition(self):
        for handler in (api.handle_citations_format, api.handle_bibliography_format):
            with self.assertRaises(ValueError):
                handler(Handler({"style": "custom-missing"}))


if __name__ == "__main__":
    unittest.main()
