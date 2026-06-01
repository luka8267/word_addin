from pathlib import Path
import unittest


TASKPANE_JS = Path(__file__).resolve().parents[1] / "bunkenn" / "word-app" / "static" / "taskpane.js"


class TaskpaneStaticTests(unittest.TestCase):
    def test_numeric_bibliography_entries_use_reference_label_format(self):
        source = TASKPANE_JS.read_text(encoding="utf-8")
        self.assertIn("return `${formatReferenceLabel(index + 1)} ${entry}`;", source)
        self.assertNotIn("return `${index + 1}. ${entry}`;", source)
