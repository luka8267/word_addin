import io
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError
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
    def test_request_supabase_maps_expired_jwt_to_permission_error(self):
        body = b'{"code":403,"error_code":"bad_jwt","msg":"invalid JWT: token is expired"}'
        error = HTTPError(
            "https://example.supabase.co/rest/v1/items",
            403,
            "Forbidden",
            {},
            io.BytesIO(body),
        )
        with patch.object(data_access, "SUPABASE_URL", "https://example.supabase.co"), patch.object(
            data_access,
            "SUPABASE_PUBLIC_KEY",
            "anon-key",
        ), patch.object(data_access, "urlopen", side_effect=error):
            with self.assertRaises(PermissionError):
                data_access.request_supabase(
                    "/rest/v1/items",
                    bearer_token="expired-token",
                    api_key="anon-key",
                )

    def test_refresh_access_token_uses_supabase_refresh_grant(self):
        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            return_value={"access_token": "next-token", "refresh_token": "next-refresh"},
        ) as request:
            result = data_access.refresh_access_token("refresh-token")

        self.assertEqual(result["access_token"], "next-token")
        request.assert_called_once()
        _, kwargs = request.call_args
        self.assertEqual(kwargs["method"], "POST")
        self.assertEqual(kwargs["query_params"], {"grant_type": "refresh_token"})
        self.assertEqual(kwargs["json_body"], {"refresh_token": "refresh-token"})

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

        self.assertIn("Journal, 12(3), 45", build_bibliography_entry(paper, "apa"))
        self.assertIn("Journal. 2024;12(3):45", build_bibliography_entry(paper, "vancouver"))


class ExtensionSaveTests(unittest.TestCase):
    def test_extension_save_creates_item_and_creator_rows(self):
        calls = []

        def stub_request(path, **kwargs):
            calls.append((path, kwargs))
            if path == "/rest/v1/paper_items_view":
                if (kwargs.get("query_params") or {}).get("select") == "display_order":
                    return [{"display_order": 41}]
                return []
            if path == "/rest/v1/items" and kwargs.get("method") == "POST":
                body = kwargs["json_body"]
                self.assertEqual(body["user_id"], "user-1")
                self.assertEqual(body["title"], "A Useful Paper")
                self.assertEqual(body["doi"], "10.1000/example")
                self.assertEqual(body["publication_title"], "Journal A")
                self.assertEqual(body["extra"]["legacy_display_order"], "42")
                return [{"id": "item-1", **body}]
            if path == "/rest/v1/creators" and kwargs.get("method") == "POST":
                self.assertEqual(
                    kwargs["json_body"],
                    [
                        {
                            "item_id": "item-1",
                            "creator_type": "author",
                            "literal_name": "Alpha",
                            "position": 1,
                        },
                        {
                            "item_id": "item-1",
                            "creator_type": "author",
                            "literal_name": "Beta",
                            "position": 2,
                        },
                    ],
                )
                return {}
            raise AssertionError(f"Unexpected request: {path} {kwargs}")

        payload = {
            "url": "https://example.org/article",
            "title": "A Useful Paper",
            "authors": ["Alpha", "Beta"],
            "journal": "Journal A",
            "year": "2026-01-02",
            "doi": "https://doi.org/10.1000/example",
            "pdfCandidates": ["/paper.pdf"],
        }
        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub_request,
        ), patch.object(data_access, "fetch_pdf_candidate", return_value=(None, "not_pdf")), patch.object(
            data_access,
            "fetch_crossref_metadata",
            return_value={},
        ):
            result = data_access.save_extension_paper(AUTH_CONTEXT, payload)

        self.assertTrue(result["saved"])
        self.assertFalse(result["duplicate"])
        self.assertEqual(result["itemId"], "item-1")
        self.assertEqual(result["doi"], "10.1000/example")
        self.assertEqual(result["pdfCandidates"], ["https://example.org/paper.pdf"])
        self.assertEqual(result["pdf"]["reason"], "not_pdf")
        self.assertIn("/rest/v1/items", [path for path, _ in calls])

    def test_extension_save_enriches_title_only_payload_from_doi_metadata(self):
        def stub_request(path, **kwargs):
            params = kwargs.get("query_params") or {}
            if path == "/rest/v1/paper_items_view" and params.get("select") != "display_order":
                return []
            if path == "/rest/v1/paper_items_view" and params.get("select") == "display_order":
                return [{"display_order": 5}]
            if path == "/rest/v1/items" and kwargs.get("method") == "POST":
                body = kwargs["json_body"]
                self.assertEqual(body["title"], "Publisher Page")
                self.assertEqual(body["publication_title"], "Crossref Journal")
                self.assertEqual(body["year"], 2026)
                self.assertEqual(body["doi"], "10.1000/example")
                self.assertEqual(body["volume"], "12")
                self.assertEqual(body["extra"]["legacy_display_order"], "6")
                return [{"id": "item-1", **body}]
            if path == "/rest/v1/creators" and kwargs.get("method") == "POST":
                self.assertEqual(kwargs["json_body"][0]["literal_name"], "Jane Smith")
                return {}
            raise AssertionError(f"Unexpected request: {path} {kwargs}")

        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub_request,
        ), patch.object(
            data_access,
            "fetch_crossref_metadata",
            return_value={
                "title": "Crossref Title",
                "authors": ["Jane Smith"],
                "journal": "Crossref Journal",
                "year": 2026,
                "doi": "10.1000/example",
                "volume": "12",
            },
        ):
            result = data_access.save_extension_paper(
                AUTH_CONTEXT,
                {
                    "url": "https://example.org/doi/10.1000/example",
                    "title": "Publisher Page",
                },
            )

        self.assertTrue(result["saved"])
        self.assertEqual(result["title"], "Publisher Page")

    def test_extension_save_returns_existing_item_for_duplicate_doi(self):
        calls = []

        def stub_request(path, **kwargs):
            calls.append((path, kwargs))
            if path == "/rest/v1/paper_items_view":
                return [
                    {
                        "id": "paper-1",
                        "item_id": "item-1",
                        "title": "Existing Paper",
                        "doi": "10.1000/example",
                    }
                ]
            raise AssertionError(f"Unexpected request: {path} {kwargs}")

        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub_request,
        ), patch.object(
            data_access,
            "fetch_crossref_metadata",
            return_value={},
        ):
            result = data_access.save_extension_paper(
                AUTH_CONTEXT,
                {"title": "Existing Paper", "doi": "doi:10.1000/example"},
            )

        self.assertFalse(result["saved"])
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["itemId"], "item-1")
        self.assertNotIn("/rest/v1/items", [path for path, _ in calls])

    def test_extension_save_matches_duplicate_doi_url_variants(self):
        doi_filters = []

        def stub_request(path, **kwargs):
            if path != "/rest/v1/paper_items_view":
                raise AssertionError(f"Unexpected request: {path} {kwargs}")
            doi_filter = (kwargs.get("query_params") or {}).get("doi")
            doi_filters.append(doi_filter)
            if doi_filter == "ilike.https://doi.org/10.1000/example":
                return [
                    {
                        "id": "paper-1",
                        "item_id": "item-1",
                        "title": "Existing URL DOI",
                        "doi": "https://doi.org/10.1000/example",
                    }
                ]
            return []

        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub_request,
        ), patch.object(
            data_access,
            "fetch_crossref_metadata",
            return_value={},
        ):
            result = data_access.save_extension_paper(
                AUTH_CONTEXT,
                {"title": "Different Landing Page Title", "doi": "10.1000/example"},
            )

        self.assertFalse(result["saved"])
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["itemId"], "item-1")
        self.assertIn("ilike.10.1000/example", doi_filters)
        self.assertIn("ilike.https://doi.org/10.1000/example", doi_filters)

    def test_extension_save_uploads_fetchable_pdf_and_creates_attachment(self):
        calls = []
        uploads = []

        def stub_request(path, **kwargs):
            calls.append((path, kwargs))
            if path == "/rest/v1/paper_items_view":
                if (kwargs.get("query_params") or {}).get("select") == "display_order":
                    return []
                return []
            if path == "/rest/v1/items" and kwargs.get("method") == "POST":
                body = kwargs["json_body"]
                self.assertEqual(body["volume"], "8")
                self.assertEqual(body["issue"], "2")
                self.assertEqual(body["pages"], "11-19")
                self.assertEqual(body["publisher"], "Publisher From Page")
                return [{"id": "item-1", **body}]
            if path == "/rest/v1/attachments" and kwargs.get("method") == "POST":
                body = kwargs["json_body"]
                self.assertEqual(body["item_id"], "item-1")
                self.assertEqual(body["user_id"], "user-1")
                self.assertEqual(body["kind"], "pdf")
                self.assertEqual(body["content_type"], "application/pdf")
                self.assertTrue(body["storage_path"].endswith(".pdf"))
                return {}
            raise AssertionError(f"Unexpected request: {path} {kwargs}")

        def stub_upload(path, body, content_type, context):
            uploads.append((path, body, content_type, context))

        with patch.object(data_access, "use_supabase", return_value=True), patch.object(
            data_access,
            "request_supabase",
            side_effect=stub_request,
        ), patch.object(
            data_access,
            "fetch_crossref_metadata",
            return_value={},
        ), patch.object(
            data_access,
            "fetch_pdf_candidate",
            return_value=(b"%PDF-1.7 fake", "ok"),
        ), patch.object(
            data_access,
            "storage_upload",
            side_effect=stub_upload,
        ):
            result = data_access.save_extension_paper(
                AUTH_CONTEXT,
                {
                    "title": "PDF Paper",
                    "url": "https://example.org/article",
                    "volume": "8",
                    "issue": "2",
                    "pages": "11-19",
                    "publisher": "Publisher From Page",
                    "pdfCandidates": ["https://example.org/paper.pdf"],
                },
            )

        self.assertTrue(result["saved"])
        self.assertTrue(result["pdf"]["saved"])
        self.assertEqual(result["pdf"]["reason"], "ok")
        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0][1], b"%PDF-1.7 fake")
        self.assertEqual(uploads[0][2], "application/pdf")
        self.assertIn("/rest/v1/attachments", [path for path, _ in calls])

    def test_extension_save_requires_authenticated_context(self):
        with patch.object(data_access, "use_supabase", return_value=True):
            with self.assertRaises(PermissionError):
                data_access.save_extension_paper({"userId": "user-1"}, {"title": "No Auth"})

    def test_extension_save_requires_auth_before_supabase_config(self):
        with patch.object(data_access, "use_supabase", return_value=False):
            with self.assertRaises(PermissionError):
                data_access.save_extension_paper({}, {"title": "No Auth"})


if __name__ == "__main__":
    unittest.main()
