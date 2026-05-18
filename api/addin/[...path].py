import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


API_ROOT = Path(__file__).resolve().parents[2] / "bunkenn" / "azure-static-web-apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from shared.bunken_service import build_bibliography_entry, build_in_text_citation
from shared.data_access import (
    build_auth_diagnostics,
    build_context_from_token,
    debug_endpoints_enabled,
    fetch_papers_by_ids,
    list_document_citations,
    login_with_password,
    resolve_request_context,
    search_user_papers,
    sync_document_citations,
)


class VercelRequest:
    def __init__(self, headers, params, payload):
        self.headers = headers
        self.params = params
        self._payload = payload

    def get_json(self):
        return self._payload or {}


class handler(BaseHTTPRequestHandler):
    def _request(self):
        parsed = urlparse(self.path)
        params = {
            key: values[0] if values else ""
            for key, values in parse_qs(parsed.query).items()
        }
        payload = {}
        if self.command in {"POST", "PUT", "PATCH"}:
            length = int(self.headers.get("Content-Length") or "0")
            raw_body = self.rfile.read(length) if length else b"{}"
            if raw_body:
                payload = json.loads(raw_body.decode("utf-8"))
        return parsed.path, VercelRequest(self.headers, params, payload)

    def _json(self, value, status=200):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _not_found(self):
        self._json({"error": "not found"}, status=404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Bunken-Access-Token, X-Bunken-User-Id, X-Bunken-Username, X-Bunken-Email",
        )
        self.end_headers()

    def do_GET(self):
        path, req = self._request()
        try:
            if path == "/api/addin/papers":
                if req.params.get("_debug") == "version":
                    if not debug_endpoints_enabled():
                        self._not_found()
                        return
                    self._json({"version": "citation-context-sync-v1"})
                    return
                papers = search_user_papers(
                    resolve_request_context(req),
                    req.params.get("q", ""),
                )
                self._json({"items": [paper.to_dict() for paper in papers]})
                return

            if path == "/api/addin/documents/citations":
                result = list_document_citations(
                    resolve_request_context(req),
                    req.params.get("wordDocumentId", ""),
                )
                self._json(result)
                return

            self._not_found()
        except Exception as error:
            self._json({"error": str(error)}, status=401 if isinstance(error, PermissionError) else 500)

    def do_POST(self):
        path, req = self._request()
        try:
            if path == "/api/addin/auth/login":
                payload = req.get_json()
                email = (payload.get("email") or "").strip()
                password = payload.get("password") or ""
                if not email or not password:
                    self._json({"error": "email and password are required"}, status=400)
                    return
                auth_response = login_with_password(email, password)
                access_token = auth_response.get("access_token") or ""
                refresh_token = auth_response.get("refresh_token") or ""
                context = build_context_from_token(access_token)
                self._json(
                    {
                        "accessToken": access_token,
                        "refreshToken": refresh_token,
                        "userId": context["userId"],
                        "email": context.get("email", ""),
                        "username": context.get("username", ""),
                    }
                )
                return

            if path == "/api/addin/auth/session":
                if req.params.get("_debug") == "env":
                    if not debug_endpoints_enabled():
                        self._not_found()
                        return
                    self._json(build_auth_diagnostics(req))
                    return
                context = resolve_request_context(req)
                if not context.get("userId"):
                    self._json({"authenticated": False})
                    return
                self._json(
                    {
                        "authenticated": True,
                        "userId": context["userId"],
                        "email": context.get("email", ""),
                        "username": context.get("username", ""),
                    }
                )
                return

            if path == "/api/addin/citations/format":
                payload = req.get_json()
                items = payload.get("items", [])
                style = payload.get("style", "vancouver")
                paper_ids = [str(item.get("paperId")) for item in items]
                papers = fetch_papers_by_ids(resolve_request_context(req), paper_ids)
                rendered_items = []
                for item, paper in zip(items, papers):
                    rendered_items.append(
                        {
                            "paperId": paper.id,
                            "renderedText": build_in_text_citation(
                                paper,
                                style=style,
                                locator=item.get("locator"),
                            ),
                        }
                    )
                self._json(
                    {
                        "text": "; ".join(item["renderedText"] for item in rendered_items),
                        "items": rendered_items,
                    }
                )
                return

            if path == "/api/addin/bibliography/format":
                payload = req.get_json()
                style = payload.get("style", "vancouver")
                paper_ids = [str(paper_id) for paper_id in payload.get("paperIds", [])]
                unique_ids = list(dict.fromkeys(paper_ids))
                papers = fetch_papers_by_ids(resolve_request_context(req), unique_ids)
                self._json(
                    {
                        "title": "References",
                        "entries": [
                            build_bibliography_entry(paper, style) for paper in papers
                        ],
                    }
                )
                return

            if path == "/api/addin/documents/sync":
                result = sync_document_citations(
                    resolve_request_context(req),
                    req.get_json(),
                )
                self._json(result)
                return

            self._not_found()
        except Exception as error:
            self._json({"error": str(error)}, status=401 if isinstance(error, PermissionError) else 500)
