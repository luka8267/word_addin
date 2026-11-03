import json
import sys
from pathlib import Path
from urllib.error import HTTPError
import unittest
from unittest.mock import Mock, patch

API_ROOT = Path(__file__).resolve().parents[1] / "bunkenn" / "word-app" / "api"
sys.path.insert(0, str(API_ROOT))
from shared import data_access


MESSAGE = {
    "DOI": "10.1021/jp953141+", "title": ["The exact paper title"],
    "author": [{"given": "Leonardo", "family": "Lo Presti"}, {"given": "Benoît", "family": "Roux"}],
    "container-title": ["Journal"], "published-print": {"date-parts": [[2025]]},
    "published-online": {"date-parts": [[2024]]}, "volume": "97", "issue": "11",
    "article-number": "0018", "page": "1-8", "publisher": "Publisher",
}


def response_for(message):
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = json.dumps({"message": message}).encode("utf-8")
    return response


class ExtensionMetadataTests(unittest.TestCase):
    def test_plus_encoding_and_chemical_doi_punctuation_survive(self):
        self.assertEqual(data_access.normalize_doi("https://doi.org/10.1021/jp953141%2B"), "10.1021/jp953141+")
        self.assertEqual(data_access.normalize_doi("doi.org/10.1002/chem.202000593"), "10.1002/chem.202000593")
        self.assertEqual(data_access.normalize_doi("10.1002/1521-3773(20020104)41:1<48::aid-anie48>3.0.co;2-u"), "10.1002/1521-3773(20020104)41:1<48::aid-anie48>3.0.co;2-u")

    def test_crossref_verification_preserves_author_structure_and_article_number(self):
        with patch.object(data_access, "urlopen", return_value=response_for(MESSAGE)) as get:
            result = data_access.fetch_crossref_metadata("10.1021/jp953141+")
        self.assertIn("%2B", get.call_args.args[0].full_url)
        self.assertEqual(result["authors"], ["Leonardo Lo Presti", "Benoît Roux"])
        self.assertEqual(result["authorDetails"][0], {"family": "Lo Presti", "given": "Leonardo"})
        self.assertEqual(result["pages"], "0018")
        self.assertEqual(result["year"], 2025)

    def test_registered_canonical_plus_is_accepted_but_unrelated_doi_is_not(self):
        with patch.object(data_access, "urlopen", return_value=response_for(MESSAGE)):
            self.assertEqual(data_access.fetch_crossref_metadata("10.1021/jp953141")["doi"], "10.1021/jp953141+")
        with patch.object(data_access, "urlopen", return_value=response_for({**MESSAGE, "DOI": "10.9999/unrelated"})):
            self.assertEqual(data_access.fetch_crossref_metadata("10.1021/jp953141+"), {})

    def test_html_suffix_is_only_corrected_when_verified(self):
        message = {**MESSAGE, "DOI": "10.1515/pac-2025-0555"}
        missing = HTTPError("https://api.crossref.org", 404, "missing", {}, None)
        with patch.object(data_access, "urlopen", side_effect=[missing, response_for(message)]):
            self.assertEqual(data_access.fetch_crossref_metadata("10.1515/pac-2025-0555/html")["doi"], "10.1515/pac-2025-0555")

    def test_exact_doi_metadata_replaces_poisoned_page_fields_but_keeps_urls(self):
        source = {"title": "Browser title | Journal", "authors": ["Lo Presti"], "journal": "Website", "url": "https://example.test/article", "pdfCandidates": ["/file.pdf"], "year": 2024, "pages": "nan"}
        with patch.object(data_access, "urlopen", return_value=response_for(MESSAGE)):
            result = data_access.merge_extension_metadata(source, data_access.fetch_crossref_metadata("10.1021/jp953141+"))
        self.assertEqual(result["title"], "The exact paper title")
        self.assertEqual(result["journal"], "Journal")
        self.assertEqual(result["authors"], ["Leonardo Lo Presti", "Benoît Roux"])
        self.assertEqual(result["url"], source["url"])
        self.assertEqual(result["pdfCandidates"], source["pdfCandidates"])
        self.assertEqual(result["pages"], "0018")

    def test_fallback_titles_and_nan_values_are_cleaned(self):
        self.assertEqual(data_access.clean_extension_title("An insight into C\uf8ffH···N"), "An insight into C-H···N")
        self.assertEqual(data_access.clean_extension_title("Modeling $$\\pi$$ interactions | Journal | Springer Nature Link"), "Modeling π interactions")
        self.assertEqual(data_access.clean_extension_title("A title - with a subtitle - Saleh - 2012 - Journal - Wiley Online Library"), "A title - with a subtitle")
        self.assertEqual(data_access.clean_extension_text(float("nan")), "")
        self.assertEqual(data_access.clean_extension_text("nan"), "")
        self.assertEqual(data_access.clean_extension_text(174.0), "174")

    def test_saving_new_item_writes_given_family_and_does_not_mutate_existing_rows(self):
        writes = []
        def request(path, **kwargs):
            if kwargs.get("method") == "POST":
                writes.append((path, kwargs["json_body"]))
                return [{"id": "i1", **kwargs["json_body"]}] if path.endswith("/items") else {}
            return []
        context = {"userId": "u1", "access_token": "test"}
        with patch.object(data_access, "use_supabase", return_value=True), patch.object(data_access, "request_supabase", side_effect=request), patch.object(data_access, "urlopen", return_value=response_for(MESSAGE)):
            result = data_access.save_extension_paper(context, {"url": "https://example.test/doi/10.1021/jp953141+", "title": "Browser title"})
        self.assertTrue(result["saved"])
        creators = next(body for path, body in writes if path.endswith("/creators"))
        self.assertEqual(creators[0]["first_name"], "Leonardo")
        self.assertEqual(creators[0]["last_name"], "Lo Presti")
        self.assertIsNone(creators[0]["literal_name"])
        self.assertTrue(all(path in {"/rest/v1/items", "/rest/v1/creators"} for path, _ in writes))

    def test_duplicate_save_never_updates_or_deletes_existing_data(self):
        def request(path, **kwargs):
            self.assertNotIn(kwargs.get("method"), {"PATCH", "POST", "DELETE"})
            return [{"id": "p1", "item_id": "i1", "title": "Manually corrected", "doi": "10.1021/jp953141+"}]
        with patch.object(data_access, "use_supabase", return_value=True), patch.object(data_access, "request_supabase", side_effect=request), patch.object(data_access, "urlopen", return_value=response_for(MESSAGE)):
            result = data_access.save_extension_paper({"userId": "u1", "access_token": "test"}, {"doi": "10.1021/jp953141+", "title": "Browser title"})
        self.assertTrue(result["duplicate"])
        self.assertEqual(result["title"], "Manually corrected")


if __name__ == "__main__":
    unittest.main()
