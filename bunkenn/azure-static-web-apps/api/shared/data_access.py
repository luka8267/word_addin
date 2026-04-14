import json
import os
import sqlite3
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
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
SAMPLE_DATA_PATH = Path(__file__).resolve().with_name("sample_papers.json")


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
    )


def extract_bearer_token(req: func.HttpRequest) -> str:
    auth_header = req.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
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
    json_body: dict | None = None,
    bearer_token: str | None = None,
    api_key: str | None = None,
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
    if DEFAULT_USER_ID:
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
    header_context = extract_header_context(req)
    if header_context:
        return header_context
    token = extract_bearer_token(req)
    if token and use_supabase():
        return build_context_from_token(token)
    return build_default_context()


def search_user_papers(context: dict[str, str], query: str) -> list[PaperSummary]:
    user_id = context.get("userId", "")

    if use_supabase() and user_id and SUPABASE_ADMIN_KEY:
        normalized_query = (query or "").strip()
        params = {
            "select": "id,title,authors,journal,year,doi,user_id",
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
        rows = request_supabase("/rest/v1/papers", query_params=params, api_key=SUPABASE_ADMIN_KEY)
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

    if use_supabase() and user_id and SUPABASE_ADMIN_KEY:
        rows = request_supabase(
            "/rest/v1/papers",
            query_params={
                "select": "id,title,authors,journal,year,doi,user_id",
                "user_id": f"eq.{user_id}",
                "id": f"in.({csv_ids})",
            },
            api_key=SUPABASE_ADMIN_KEY,
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
