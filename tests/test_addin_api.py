import sys
import unittest
from pathlib import Path
from unittest.mock import patch


API_ROOT = Path(__file__).resolve().parents[1] / "bunkenn" / "word-app" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from shared import data_access
from shared.bunken_models import PaperSummary
from shared.bunken_service import build_bibliography_entry, build_in_text_citation


AUTH_CONTEXT = {
    "access_token": "token",
    "userId": "user-1",
    "email": "user@example.com",
    "username": "user",
}


class SupabaseStub:
    def __init__(self):
        self.calls = []

    def request(self, path, **kwargs):
        self.calls.append((path, kwargs))
        params = kwargs.get("query_params") or {}
        method = kwargs.get("method", "GET")

        if path == "/rest/v1/paper_items_view" and method == "GET":
            ids_filter = params.get("id", "")
            rows = [
                {
                    "id": "paper-2",
                    "title": "Second",
                    "authors": "Beta",
                    "journal": "Journal B",
                    "year": 2025,
                    "doi": None,
                    "volume": "12",
                    "issue": "2",
                    "pages": "10-20",
                    "publisher": "Publisher B",
                    "item_type": "journalArticle",
                    "user_id": "user-1",
                },
                {
                    "id": "paper-1",
                    "title": "First",
                    "authors": "Alpha",
                    "journal": "Journal A",
                    "year": 2024,
                    "doi": "10.1000/example",
                    "volume": "42",
                    "issue": "1",
                    "pages": "100-110",
                    "publisher": "Publisher A",
                    "item_type": "journalArticle",
                    "user_id": "user-1",
                },
            ]
            if ids_filter:
                wanted = ids_filter.removeprefix("in.(").removesuffix(")").split(",")
                return [row for row in rows if row["id"] in wanted]
            return rows

        if path == "/rest/v1/documents" and method == "POST":
            return [{"id": "doc-db-id"}]

        if path == "/rest/v1/document_citations" and method == "DELETE":
            return {}

        if path == "/rest/v1/document_citations" and method == "POST":
            return {}

        raise AssertionError(f"Unexpected request: {path} {kwargs}")


class AddinDataAccessTests(unittest.TestCase):
    def test_fetch_papers_by_ids_preserves_requested_order(self):
        stub = SupabaseStub()
        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub.request,
        ):
            papers = data_access.fetch_papers_by_ids(
                AUTH_CONTEXT,
                ["paper-1", "paper-2"],
            )

        self.assertEqual([paper.id for paper in papers], ["paper-1", "paper-2"])
        self.assertEqual(papers[0].doi, "10.1000/example")
        self.assertEqual(papers[0].volume, "42")

    def test_search_user_papers_requires_supabase_auth(self):
        with patch.object(data_access, "use_supabase", return_value=True):
            with self.assertRaises(PermissionError):
                data_access.search_user_papers({"userId": "user-1"}, "")

    def test_search_user_papers_uses_paper_items_view(self):
        stub = SupabaseStub()
        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub.request,
        ):
            papers = data_access.search_user_papers(AUTH_CONTEXT, "alpha")

        self.assertEqual([paper.id for paper in papers], ["paper-2", "paper-1"])
        path, kwargs = stub.calls[0]
        self.assertEqual(path, "/rest/v1/paper_items_view")
        self.assertEqual(kwargs["query_params"]["user_id"], "eq.user-1")
        self.assertIn("title.ilike.*alpha*", kwargs["query_params"]["or"])

    def test_sync_document_citations_writes_document_and_citations(self):
        stub = SupabaseStub()
        payload = {
            "wordDocumentId": "word-doc-1",
            "title": "Manuscript",
            "style": "vancouver",
            "locale": "ja-JP",
            "citations": [
                {
                    "citationId": "cit-1",
                    "controlId": "42",
                    "renderedText": "[1]",
                    "contextText": "この論文では重要な知見が示されている[1]。",
                    "sortOrder": 1,
                    "items": [
                        {
                            "paperId": "paper-1",
                            "locator": "p. 10",
                            "referenceNumber": 1,
                        }
                    ],
                }
            ],
        }

        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub.request,
        ):
            result = data_access.sync_document_citations(AUTH_CONTEXT, payload)

        self.assertEqual(result["documentId"], "doc-db-id")
        self.assertEqual(result["citationCount"], 1)
        self.assertTrue(result["syncedAt"])
        citation_post = [
            kwargs
            for path, kwargs in stub.calls
            if path == "/rest/v1/document_citations"
            and kwargs.get("method") == "POST"
        ][0]
        self.assertEqual(citation_post["json_body"][0]["document_id"], "doc-db-id")
        self.assertEqual(
            citation_post["json_body"][0]["citation_items"],
            [{"paperId": "paper-1", "locator": "p. 10", "referenceNumber": 1}],
        )
        self.assertEqual(
            citation_post["json_body"][0]["context_text"],
            "この論文では重要な知見が示されている[1]。",
        )


class AddinCitationFormatTests(unittest.TestCase):
    def test_numeric_styles_use_reference_label(self):
        paper = PaperSummary(
            id="paper-1",
            title="Title",
            authors="Alpha, Beta",
            journal="Journal",
            year=2024,
        )

        self.assertEqual(build_in_text_citation(paper, "vancouver"), "[paper-1]")
        self.assertEqual(build_in_text_citation(paper, "vancouver", "p. 3"), "[paper-1, p. 3]")

    def test_author_year_fallback(self):
        paper = PaperSummary(
            id="paper-1",
            title="Title",
            authors="Alpha, Beta",
            journal="Journal",
            year=2024,
        )

        self.assertEqual(build_in_text_citation(paper, "apa"), "(Alpha & Beta, 2024)")
        self.assertIn("Title", build_bibliography_entry(paper, "apa"))

    def test_author_year_uses_et_al_for_three_or_more_authors(self):
        paper = PaperSummary(
            id="paper-1",
            title="Title",
            authors="Alpha, Beta, Gamma",
            journal="Journal",
            year=2024,
        )

        self.assertEqual(build_in_text_citation(paper, "apa"), "(Alpha et al., 2024)")

    def test_bibliography_entries_include_doi(self):
        paper = PaperSummary(
            id="paper-1",
            title="Title",
            authors="Alpha, Beta",
            journal="Journal",
            year=2024,
            doi="10.1000/example",
        )

        self.assertIn("https://doi.org/10.1000/example", build_bibliography_entry(paper, "apa"))
        self.assertIn("doi: 10.1000/example", build_bibliography_entry(paper, "vancouver"))

    def test_bibliography_entries_include_publication_metadata(self):
        paper = PaperSummary(
            id="paper-1",
            title="Title",
            authors="Alpha",
            journal="Journal",
            year=2024,
            volume="12",
            issue="3",
            pages="45-67",
        )

        self.assertIn("Journal 12(3), 45-67", build_bibliography_entry(paper, "apa"))
        self.assertIn("Journal, 12(3), 45-67", build_bibliography_entry(paper, "vancouver"))


if __name__ == "__main__":
    unittest.main()
