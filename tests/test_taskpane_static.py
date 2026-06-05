from pathlib import Path
import unittest


TASKPANE_JS = Path(__file__).resolve().parents[1] / "bunkenn" / "word-app" / "static" / "taskpane.js"


class TaskpaneStaticTests(unittest.TestCase):
    def test_numeric_bibliography_entries_use_reference_label_format(self):
        source = TASKPANE_JS.read_text(encoding="utf-8")
        self.assertIn("return `${formatReferenceLabel(index + 1)} ${stripLeadingBibliographyNumber(entry)}`;", source)
        self.assertIn('replace(/^\\s*(?:\\[\\d+\\]|\\d+[\\.)])\\s*/, "")', source)
        self.assertNotIn("return `${index + 1}. ${entry}`;", source)

    def test_bibliography_applies_document_end_font_after_html_insert(self):
        source = TASKPANE_JS.read_text(encoding="utf-8")
        self.assertIn('bodyEnd.load("font/name,font/size");', source)
        self.assertIn("const bibliographyRange = control.getRange();", source)
        self.assertIn("bibliographyRange.font.name = bibliographyFontName;", source)
        self.assertIn("bibliographyRange.font.size = bibliographyFontSize;", source)

    def test_multiple_citation_editor_shows_locator_guidance(self):
        source = TASKPANE_JS.read_text(encoding="utf-8")
        self.assertIn("この複数文献引用全体に適用されます", source)
        self.assertIn("ページ番号を付ける場合", source)
