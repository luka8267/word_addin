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

    def test_consecutive_numeric_citations_use_one_compact_range_label(self):
        source = TASKPANE_JS.read_text(encoding="utf-8")
        self.assertIn("const rangeLength = range[1] - range[0] + 1;", source)
        self.assertIn("if (rangeLength >= 3)", source)
        self.assertIn('return `${range[0]}-${range[1]})`;', source)
        self.assertIn('return `${range[0]})${range[1]})`;', source)
        self.assertNotIn('`${range[0]})-${range[1]})`', source)

    def test_superscript_citations_keep_ascii_digits_and_use_word_formatting(self):
        source = TASKPANE_JS.read_text(encoding="utf-8")
        self.assertIn("control.insertText(referenceLabel, Word.InsertLocation.replace);", source)
        self.assertIn("const citationRange = control.getRange();", source)
        self.assertIn("citationRange.font.superscript = shouldSuperscriptStyle(style);", source)
        self.assertNotIn("control.insertText(displayLabel, Word.InsertLocation.replace);", source)

    def test_multiple_citation_editor_shows_locator_guidance(self):
        source = TASKPANE_JS.read_text(encoding="utf-8")
        self.assertIn("この複数文献引用全体に適用されます", source)
        self.assertIn("ページ番号を付ける場合", source)
        self.assertIn("引用のページ番号を保存し、参考文献を更新しました。", source)

    def test_taskpane_uses_user_facing_page_number_label(self):
        html = (TASKPANE_JS.parent / "taskpane.html").read_text(encoding="utf-8")
        self.assertIn("ページ番号を保存", html)
        self.assertIn("ページ番号・位置", html)
        self.assertNotIn(">locatorを保存<", html)
