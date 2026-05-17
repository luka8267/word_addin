import base64
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import azure.functions as func

from .bunken_models import PaperSummary


DB_PATH = Path(os.getenv("BUNKEN_DB_PATH", str(Path(__file__).resolve().parents[3] / "papers.db")))
DEFAULT_USER_ID = os.getenv("BUNKEN_DEFAULT_USER_ID", "")
DEFAULT_EMAIL = os.getenv("BUNKEN_DEFAULT_EMAIL", "")
DEFAULT_USERNAME = os.getenv("BUNKEN_DEFAULT_USERNAME", "cloud-user")
SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").rstrip("/")
SUPABASE_ADMIN_KEY = os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
SUPABASE_PUBLIC_KEY = (
    os.getenv("SUPABASE_PUBLISHABLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
    or SUPABASE_ADMIN_KEY
)
DEBUG_ENDPOINTS_ENABLED = os.getenv("BUNKEN_ENABLE_DEBUG_ENDPOINTS", "").lower() in {
    "1",
    "true",
    "yes",
}
SAMPLE_DATA_PATH = Path(__file__).resolve().with_name("sample_papers.json")
PAPER_SELECT_COLUMNS = "id,title,authors,journal,year,doi,user_id,volume,issue,pages,publisher,item_type"
LEGACY_PAPER_SELECT_COLUMNS = "id,title,authors,journal,year,doi,user_id"


def decode_jwt_payload_unverified(token: str) -> dict:
    parts = (token or "").split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
        value = json.loads(decoded.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def extract_supabase_ref_from_url(url: str) -> str:
    hostname = urlparse(url or "").hostname or ""
    if hostname.endswith(".supabase.co"):
        return hostname.split(".", maxsplit=1)[0]
    return ""


def is_supabase_access_token(token: str) -> bool:
    payload = decode_jwt_payload_unverified(token)
    issuer = payload.get("iss", "") or ""
    return bool(
        token
        and issuer
        and extract_supabase_ref_from_url(issuer)
        == extract_supabase_ref_from_url(SUPABASE_URL)
    )


def debug_endpoints_enabled() -> bool:
    return DEBUG_ENDPOINTS_ENABLED


def build_auth_diagnostics(req: func.HttpRequest) -> dict:
    token = extract_bearer_token(req)
    payload = decode_jwt_payload_unverified(token)
    issuer = payload.get("iss", "") or ""
    custom_token = (req.headers.get("x-bunken-access-token") or "").strip()
    return {
        "supabaseUrlHost": urlparse(SUPABASE_URL).hostname or "",
        "supabaseUrlRef": extract_supabase_ref_from_url(SUPABASE_URL),
        "hasSupabaseAnonKey": bool(os.getenv("SUPABASE_ANON_KEY")),
        "hasSupabasePublishableKey": bool(os.getenv("SUPABASE_PUBLISHABLE_KEY")),
        "hasSupabaseServiceRoleKey": bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
        "hasSupabaseKey": bool(os.getenv("SUPABASE_KEY")),
        "publicKeySource": (
            "SUPABASE_PUBLISHABLE_KEY"
            if os.getenv("SUPABASE_PUBLISHABLE_KEY")
            else "SUPABASE_ANON_KEY"
            if os.getenv("SUPABASE_ANON_KEY")
            else "SUPABASE_ADMIN_KEY"
            if SUPABASE_ADMIN_KEY
            else ""
        ),
        "adminKeySource": (
            "SUPABASE_KEY"
            if os.getenv("SUPABASE_KEY")
            else "SUPABASE_SERVICE_ROLE_KEY"
            if os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            else ""
        ),
        "tokenPresent": bool(token),
        "customTokenPresent": bool(custom_token),
        "authorizationHeaderPresent": bool(req.headers.get("authorization", "")),
        "tokenIssuer": issuer,
        "tokenIssuerRef": extract_supabase_ref_from_url(issuer),
        "tokenRole": payload.get("role", ""),
        "tokenSubjectPresent": bool(payload.get("sub")),
    }


def load_sample_papers() -> list[PaperSummary]:
    if not SAMPLE_DATA_PATH.exists():
        return []
    items = json.loads(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
    return [paper_from_mapping(item) for item in items]


def use_supabase() -> bool:
    return bool(SUPABASE_URL and (SUPABASE_PUBLIC_KEY or SUPABASE_ADMIN_KEY))


def use_sqlite() -> bool:
    return DB_PATH.exists()


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def paper_from_mapping(item: dict) -> PaperSummary:
    return PaperSummary(
        id=str(item.get("id", "")),
        title=item.get("title", "") or "",
        authors=item.get("authors", "") or "",
        journal=item.get("journal", "") or "",
        year=int(item.get("year", 0) or 0),
        doi=item.get("doi"),
        volume=item.get("volume", "") or "",
        issue=item.get("issue", "") or "",
        pages=item.get("pages", "") or "",
        publisher=item.get("publisher", "") or "",
        item_type=item.get("item_type", "") or "journalArticle",
    )


def extract_bearer_token(req: func.HttpRequest) -> str:
    custom_token = (req.headers.get("x-bunken-access-token") or "").strip()
    if is_supabase_access_token(custom_token):
        return custom_token

    auth_header = req.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if is_supabase_access_token(token):
            return token
    return ""


def extract_header_context(req: func.HttpRequest) -> dict[str, str]:
    user_id = (req.headers.get("x-bunken-user-id") or "").strip()
    if not user_id:
        return {}
    return {
        "access_token": "",
        "userId": user_id,
        "email": (req.headers.get("x-bunken-email") or "").strip(),
        "username": (req.headers.get("x-bunken-username") or "").strip() or DEFAULT_USERNAME,
    }


def request_supabase(
    path: str,
    method: str = "GET",
    query_params: dict[str, str] | None = None,
    json_body: dict | list | None = None,
    bearer_token: str | None = None,
    api_key: str | None = None,
    prefer: str | None = None,
) -> dict | list[dict]:
    query_string = ""
    if query_params:
        query_string = f"?{urlencode(query_params, safe='(),.*')}"
    url = f"{SUPABASE_URL}{path}{query_string}"
    body = None
    resolved_api_key = api_key or SUPABASE_PUBLIC_KEY or SUPABASE_ADMIN_KEY
    headers = {
        "apikey": resolved_api_key,
        "Accept": "application/json",
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    elif api_key == SUPABASE_ADMIN_KEY and SUPABASE_ADMIN_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_ADMIN_KEY}"
    if prefer:
        headers["Prefer"] = prefer
    if json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=headers, method=method)

    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase request failed: {error.code} {error_body}") from error


def is_missing_metadata_column_error(error: Exception) -> bool:
    error_text = str(error).lower()
    if "could not find" not in error_text and "column" not in error_text:
        return False
    return any(
        column in error_text
        for column in ("volume", "issue", "pages", "publisher", "item_type")
    )


def login_with_password(email: str, password: str) -> dict:
    if not use_supabase():
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLIC_KEY are required for login")
    return request_supabase(
        "/auth/v1/token",
        method="POST",
        query_params={"grant_type": "password"},
        json_body={"email": email, "password": password},
        api_key=SUPABASE_PUBLIC_KEY,
    )


def fetch_user_from_token(access_token: str) -> dict:
    if not access_token:
        raise RuntimeError("Missing access token")
    return request_supabase("/auth/v1/user", bearer_token=access_token, api_key=SUPABASE_PUBLIC_KEY)


def build_context_from_token(access_token: str) -> dict[str, str]:
    user = fetch_user_from_token(access_token)
    user_metadata = user.get("user_metadata") or {}
    email = user.get("email") or ""
    username = (
        user_metadata.get("username")
        or (email.split("@", maxsplit=1)[0] if email and "@" in email else "")
        or DEFAULT_USERNAME
    )
    return {
        "access_token": access_token,
        "userId": str(user["id"]),
        "email": email,
        "username": username,
    }


def build_default_context() -> dict[str, str]:
    if DEFAULT_USER_ID and not use_supabase():
        return {
            "access_token": "",
            "userId": DEFAULT_USER_ID,
            "email": DEFAULT_EMAIL,
            "username": DEFAULT_USERNAME,
        }
    return {
        "access_token": "",
        "userId": "",
        "email": "",
        "username": DEFAULT_USERNAME,
    }


def resolve_request_context(req: func.HttpRequest) -> dict[str, str]:
    token = extract_bearer_token(req)
    if token and use_supabase():
        return build_context_from_token(token)
    if not use_supabase():
        header_context = extract_header_context(req)
        if header_context:
            return header_context
    return build_default_context()


def supabase_request_auth(context: dict[str, str]) -> dict[str, str | None]:
    access_token = context.get("access_token") or ""
    if access_token:
        return {"api_key": SUPABASE_PUBLIC_KEY, "bearer_token": access_token}
    return {"api_key": SUPABASE_ADMIN_KEY, "bearer_token": None}


def search_user_papers(context: dict[str, str], query: str) -> list[PaperSummary]:
    user_id = context.get("userId", "")

    if use_supabase():
        if not user_id or not context.get("access_token"):
            raise PermissionError("Authentication required")
        normalized_query = (query or "").strip()
        params = {
            "select": PAPER_SELECT_COLUMNS,
            "user_id": f"eq.{user_id}",
            "order": "display_order.asc.nullslast,id.asc",
        }
        if normalized_query:
            escaped_query = normalized_query.replace("%", r"\%").replace(",", r"\,")
            params["or"] = (
                f"(title.ilike.*{escaped_query}*,"
                f"authors.ilike.*{escaped_query}*,"
                f"journal.ilike.*{escaped_query}*)"
            )
        auth = supabase_request_auth(context)
        try:
            rows = request_supabase(
                "/rest/v1/paper_items_view",
                query_params=params,
                bearer_token=auth["bearer_token"],
                api_key=auth["api_key"],
            )
        except RuntimeError as error:
            if not is_missing_metadata_column_error(error):
                raise
            params["select"] = LEGACY_PAPER_SELECT_COLUMNS
            rows = request_supabase(
                "/rest/v1/paper_items_view",
                query_params=params,
                bearer_token=auth["bearer_token"],
                api_key=auth["api_key"],
            )
        return [paper_from_mapping(row) for row in rows]

    if use_sqlite():
        normalized_query = f"%{(query or '').strip()}%"
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT id, title, authors, journal, year, doi
                FROM papers
                WHERE user_id = ?
                  AND (
                    ? = '%%'
                    OR title LIKE ?
                    OR authors LIKE ?
                    OR journal LIKE ?
                  )
                ORDER BY COALESCE(display_order, id)
                """,
                (user_id or "1", normalized_query, normalized_query, normalized_query, normalized_query),
            ).fetchall()
        return [
            PaperSummary(
                id=str(row["id"]),
                title=row["title"] or "",
                authors=row["authors"] or "",
                journal=row["journal"] or "",
                year=int(row["year"] or 0),
                doi=row["doi"],
            )
            for row in rows
        ]

    normalized_query = (query or "").strip().lower()
    papers = load_sample_papers()
    if not normalized_query:
        return papers
    return [
        paper
        for paper in papers
        if normalized_query in paper.title.lower()
        or normalized_query in paper.authors.lower()
        or normalized_query in paper.journal.lower()
    ]


def fetch_papers_by_ids(context: dict[str, str], paper_ids: list[str]) -> list[PaperSummary]:
    if not paper_ids:
        return []

    user_id = context.get("userId", "")
    csv_ids = ",".join(paper_ids)

    if use_supabase():
        if not user_id or not context.get("access_token"):
            raise PermissionError("Authentication required")
        auth = supabase_request_auth(context)
        params = {
            "select": PAPER_SELECT_COLUMNS,
            "user_id": f"eq.{user_id}",
            "id": f"in.({csv_ids})",
        }
        try:
            rows = request_supabase(
                "/rest/v1/paper_items_view",
                query_params=params,
                bearer_token=auth["bearer_token"],
                api_key=auth["api_key"],
            )
        except RuntimeError as error:
            if not is_missing_metadata_column_error(error):
                raise
            params["select"] = LEGACY_PAPER_SELECT_COLUMNS
            rows = request_supabase(
                "/rest/v1/paper_items_view",
                query_params=params,
                bearer_token=auth["bearer_token"],
                api_key=auth["api_key"],
            )
        by_id = {str(row["id"]): paper_from_mapping(row) for row in rows}
        return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]

    if use_sqlite():
        placeholders = ",".join("?" for _ in paper_ids)
        params = [user_id or "1", *paper_ids]
        with get_connection() as connection:
            rows = connection.execute(
                f"""
                SELECT id, title, authors, journal, year, doi
                FROM papers
                WHERE user_id = ?
                  AND id IN ({placeholders})
                """,
                params,
            ).fetchall()
        by_id = {
            str(row["id"]): PaperSummary(
                id=str(row["id"]),
                title=row["title"] or "",
                authors=row["authors"] or "",
                journal=row["journal"] or "",
                year=int(row["year"] or 0),
                doi=row["doi"],
            )
            for row in rows
        }
        return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]

    by_id = {paper.id: paper for paper in load_sample_papers()}
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _citation_item_payload(item: dict) -> dict:
    return {
        "paperId": str(item.get("paperId") or ""),
        "locator": item.get("locator") or None,
        "referenceNumber": item.get("referenceNumber"),
    }


def _paper_map_for_ids(context: dict[str, str], paper_ids: list[str]) -> dict[str, PaperSummary]:
    unique_ids = list(dict.fromkeys(str(paper_id) for paper_id in paper_ids if paper_id))
    return {paper.id: paper for paper in fetch_papers_by_ids(context, unique_ids)}


def list_document_citations(context: dict[str, str], word_document_id: str) -> dict:
    user_id = context.get("userId", "")
    if not use_supabase():
        return {"document": None, "citations": []}
    if not user_id or not context.get("access_token"):
        raise PermissionError("Authentication required")
    normalized_document_id = (word_document_id or "").strip()
    if not normalized_document_id:
        raise ValueError("wordDocumentId is required")

    auth = supabase_request_auth(context)
    document_rows = request_supabase(
        "/rest/v1/documents",
        query_params={
            "select": "id,word_document_id,title,citation_style,updated_at",
            "user_id": f"eq.{user_id}",
            "word_document_id": f"eq.{normalized_document_id}",
            "limit": "1",
        },
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    if not isinstance(document_rows, list) or not document_rows:
        return {"document": None, "citations": []}

    document = document_rows[0]
    citation_rows = request_supabase(
        "/rest/v1/document_citations",
        query_params={
            "select": (
                "id,citation_key,word_control_id,citation_items,rendered_text,"
                "context_text,sort_order,updated_at"
            ),
            "document_id": f"eq.{document['id']}",
            "order": "sort_order.asc,created_at.asc",
        },
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    citation_list = citation_rows if isinstance(citation_rows, list) else []
    paper_ids = []
    for row in citation_list:
        for item in row.get("citation_items") or []:
            paper_id = str(item.get("paperId") or "")
            if paper_id:
                paper_ids.append(paper_id)
    papers_by_id = _paper_map_for_ids(context, paper_ids)

    citations = []
    for row in citation_list:
        items = []
        for item in row.get("citation_items") or []:
            paper_id = str(item.get("paperId") or "")
            paper = papers_by_id.get(paper_id)
            items.append(
                {
                    "paperId": paper_id,
                    "locator": item.get("locator"),
                    "referenceNumber": item.get("referenceNumber"),
                    "paper": paper.to_dict() if paper else None,
                }
            )
        citations.append(
            {
                "citationId": row.get("citation_key") or "",
                "controlId": row.get("word_control_id") or "",
                "renderedText": row.get("rendered_text") or "",
                "contextText": row.get("context_text") or "",
                "sortOrder": row.get("sort_order") or 0,
                "updatedAt": row.get("updated_at") or "",
                "items": items,
            }
        )

    return {
        "document": {
            "id": document.get("id"),
            "wordDocumentId": document.get("word_document_id"),
            "title": document.get("title") or "",
            "style": document.get("citation_style") or "",
            "updatedAt": document.get("updated_at") or "",
        },
        "citations": citations,
    }


def sync_document_citations(context: dict[str, str], payload: dict) -> dict:
    user_id = context.get("userId", "")
    if not use_supabase():
        return {"synced": False, "reason": "supabase_not_configured", "citationCount": 0}
    if not user_id or not context.get("access_token"):
        raise PermissionError("Authentication required")

    word_document_id = str(payload.get("wordDocumentId") or "").strip()
    if not word_document_id:
        raise ValueError("wordDocumentId is required")

    auth = supabase_request_auth(context)
    now = _utc_now_iso()
    document_rows = request_supabase(
        "/rest/v1/documents",
        method="POST",
        query_params={"on_conflict": "user_id,word_document_id"},
        json_body={
            "user_id": user_id,
            "word_document_id": word_document_id,
            "title": str(payload.get("title") or "")[:500],
            "citation_style": str(payload.get("style") or "vancouver"),
            "locale": str(payload.get("locale") or "ja-JP"),
            "updated_at": now,
        },
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
        prefer="resolution=merge-duplicates,return=representation",
    )
    if not isinstance(document_rows, list) or not document_rows:
        raise RuntimeError("Document sync did not return a document row")

    document_id = str(document_rows[0]["id"])
    request_supabase(
        "/rest/v1/document_citations",
        method="DELETE",
        query_params={"document_id": f"eq.{document_id}"},
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )

    citation_rows = []
    for index, citation in enumerate(payload.get("citations") or []):
        citation_key = str(citation.get("citationId") or "").strip()
        if not citation_key:
            continue
        items = [
            _citation_item_payload(item)
            for item in citation.get("items", [])
            if item and item.get("paperId")
        ]
        if not items:
            continue
        citation_rows.append(
            {
                "document_id": document_id,
                "citation_key": citation_key,
                "word_control_id": str(citation.get("controlId") or ""),
                "citation_items": items,
                "rendered_text": str(citation.get("renderedText") or ""),
                "context_text": str(citation.get("contextText") or "")[:2000],
                "sort_order": int(citation.get("sortOrder") or index + 1),
                "updated_at": now,
            }
        )

    if citation_rows:
        request_supabase(
            "/rest/v1/document_citations",
            method="POST",
            json_body=citation_rows,
            bearer_token=auth["bearer_token"],
            api_key=auth["api_key"],
            prefer="return=minimal",
        )

    return {
        "synced": True,
        "documentId": document_id,
        "citationCount": len(citation_rows),
        "syncedAt": now,
    }
