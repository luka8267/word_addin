import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse


API_ROOT = Path(__file__).resolve().parents[1] / "bunkenn" / "azure-static-web-apps" / "api"
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


class BunkenHandler(BaseHTTPRequestHandler):
    def request_parts(self):
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
        return VercelRequest(self.headers, params, payload)

    def json_response(self, value, status=200):
        body = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_error(self, error):
        self.json_response(
            {"error": str(error)},
            status=401 if isinstance(error, PermissionError) else 500,
        )

    def options_response(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, X-Bunken-Access-Token, X-Bunken-User-Id, X-Bunken-Username, X-Bunken-Email",
        )
        self.end_headers()


def handle_auth_login(handler):
    req = handler.request_parts()
    payload = req.get_json()
    email = (payload.get("email") or "").strip()
    password = payload.get("password") or ""
    if not email or not password:
        handler.json_response({"error": "email and password are required"}, status=400)
        return
    auth_response = login_with_password(email, password)
    access_token = auth_response.get("access_token") or ""
    refresh_token = auth_response.get("refresh_token") or ""
    context = build_context_from_token(access_token)
    handler.json_response(
        {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "userId": context["userId"],
            "email": context.get("email", ""),
            "username": context.get("username", ""),
        }
    )


def handle_auth_session(handler):
    req = handler.request_parts()
    if req.params.get("_debug") == "env":
        if not debug_endpoints_enabled():
            handler.json_response({"error": "not found"}, status=404)
            return
        handler.json_response(build_auth_diagnostics(req))
        return
    context = resolve_request_context(req)
    if not context.get("userId"):
        handler.json_response({"authenticated": False})
        return
    handler.json_response(
        {
            "authenticated": True,
            "userId": context["userId"],
            "email": context.get("email", ""),
            "username": context.get("username", ""),
        }
    )


def handle_papers(handler):
    req = handler.request_parts()
    if req.params.get("_debug") == "version":
        if not debug_endpoints_enabled():
            handler.json_response({"error": "not found"}, status=404)
            return
        handler.json_response({"version": "citation-context-sync-v1"})
        return
    papers = search_user_papers(resolve_request_context(req), req.params.get("q", ""))
    handler.json_response({"items": [paper.to_dict() for paper in papers]})


def handle_citations_format(handler):
    req = handler.request_parts()
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
    handler.json_response(
        {
            "text": "; ".join(item["renderedText"] for item in rendered_items),
            "items": rendered_items,
        }
    )


def handle_bibliography_format(handler):
    req = handler.request_parts()
    payload = req.get_json()
    style = payload.get("style", "vancouver")
    paper_ids = [str(paper_id) for paper_id in payload.get("paperIds", [])]
    unique_ids = list(dict.fromkeys(paper_ids))
    papers = fetch_papers_by_ids(resolve_request_context(req), unique_ids)
    handler.json_response(
        {
            "title": "References",
            "entries": [build_bibliography_entry(paper, style) for paper in papers],
        }
    )


def handle_documents_citations(handler):
    req = handler.request_parts()
    result = list_document_citations(
        resolve_request_context(req),
        req.params.get("wordDocumentId", ""),
    )
    handler.json_response(result)


def handle_documents_sync(handler):
    req = handler.request_parts()
    result = sync_document_citations(resolve_request_context(req), req.get_json())
    handler.json_response(result)
