import base64
import json
import ipaddress
import os
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

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
EXTENSION_PAPER_SELECT_COLUMNS = "id,item_id,title,authors,journal,year,doi,user_id,volume,issue,pages,publisher,item_type"
PDF_STORAGE_BUCKET = os.getenv("BUNKEN_PDF_STORAGE_BUCKET", "paper-pdfs")
MAX_EXTENSION_PDF_BYTES = int(os.getenv("BUNKEN_EXTENSION_MAX_PDF_BYTES", str(25 * 1024 * 1024)))
DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)



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



def normalize_doi(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = unquote(text)
    text = re.sub(r"^doi:\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text, flags=re.IGNORECASE).strip()
    text = text.strip(". ,;\t\r\n")
    match = DOI_PATTERN.search(text)
    return match.group(0).rstrip(". ,;") if match else text


def doi_lookup_values(value: str | None) -> list[str]:
    doi = normalize_doi(value)
    if not doi:
        return []
    return list(
        dict.fromkeys(
            [
                doi,
                f"doi:{doi}",
                f"doi: {doi}",
                f"https://doi.org/{doi}",
                f"http://doi.org/{doi}",
                f"https://dx.doi.org/{doi}",
                f"http://dx.doi.org/{doi}",
            ]
        )
    )


def normalize_title_key(value: str | None) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def parse_year(value) -> int | None:
    if value is None:
        return None
    match = re.search(r"(?:19|20)\d{2}", str(value))
    return int(match.group(0)) if match else None


def clean_extension_text(value: str | None, max_length: int = 2000) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())[:max_length]


def normalize_author_list(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        candidates = value
    else:
        candidates = re.split(r"\s*(?:;|\band\b|\|)\s*", str(value))
    names: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        name = clean_extension_text(item, 300).strip(" ,;")
        if not name:
            continue
        key = name.lower()
        if key not in seen:
            names.append(name)
            seen.add(key)
    return names[:50]


def extract_doi_from_values(*values) -> str:
    for value in values:
        doi = normalize_doi(value)
        if doi and DOI_PATTERN.search(doi):
            return doi
    return ""


def fetch_crossref_metadata(doi: str) -> dict:
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        return {}
    url = f"https://api.crossref.org/works/{quote(normalized_doi, safe='')}"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "bunken-extension/1.0 (mailto:metadata@bunken.local)",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return {}

    message = payload.get("message") if isinstance(payload, dict) else {}
    if not isinstance(message, dict):
        return {}
    authors = []
    for author in message.get("author") or []:
        if not isinstance(author, dict):
            continue
        literal = clean_extension_text(
            " ".join(
                part
                for part in (author.get("given"), author.get("family"))
                if part
            ),
            300,
        )
        if literal:
            authors.append(literal)

    issued_parts = (
        ((message.get("published-print") or {}).get("date-parts"))
        or ((message.get("published-online") or {}).get("date-parts"))
        or ((message.get("issued") or {}).get("date-parts"))
        or []
    )
    year = None
    if issued_parts and issued_parts[0]:
        year = parse_year(issued_parts[0][0])

    return {
        "title": clean_extension_text((message.get("title") or [""])[0], 1000),
        "authors": authors,
        "journal": clean_extension_text(
            (message.get("container-title") or message.get("short-container-title") or [""])[0],
            1000,
        ),
        "year": year,
        "doi": normalize_doi(message.get("DOI") or normalized_doi),
        "url": clean_extension_text(message.get("URL") or "", 2000),
        "publisher": clean_extension_text(message.get("publisher") or "", 1000),
        "volume": clean_extension_text(message.get("volume") or "", 100),
        "issue": clean_extension_text(message.get("issue") or "", 100),
        "pages": clean_extension_text(message.get("page") or "", 200),
        "abstract": clean_extension_text(message.get("abstract") or "", 10000),
    }


def merge_extension_metadata(source: dict, metadata: dict) -> dict:
    if not metadata:
        return source
    merged = dict(source)
    for field in ("title", "journal", "url", "abstract"):
        if not merged.get(field) and metadata.get(field):
            merged[field] = metadata[field]
    for field in ("year", "volume", "issue", "pages", "publisher"):
        if not merged.get(field) and metadata.get(field):
            merged[field] = metadata[field]
    if not merged.get("doi") and metadata.get("doi"):
        merged["doi"] = metadata["doi"]
    if not merged.get("authors") and metadata.get("authors"):
        merged["authors"] = metadata["authors"]
    return merged


def extension_source_from_payload(payload: dict) -> dict:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    source_url = clean_extension_text(payload.get("url") or metadata.get("url"), 2000)
    pdf_candidates = []
    for value in payload.get("pdfCandidates") or metadata.get("pdfCandidates") or []:
        candidate = clean_extension_text(value, 2000)
        if candidate and candidate not in pdf_candidates:
            pdf_candidates.append(candidate)
    doi = extract_doi_from_values(
        payload.get("doi"),
        metadata.get("doi"),
        metadata.get("citation_doi"),
        source_url,
        payload.get("title"),
    )
    return {
        "title": clean_extension_text(payload.get("title") or metadata.get("title") or metadata.get("citation_title"), 1000),
        "authors": normalize_author_list(payload.get("authors") or metadata.get("authors") or metadata.get("citation_authors")),
        "journal": clean_extension_text(payload.get("journal") or metadata.get("journal") or metadata.get("citation_journal_title"), 1000),
        "year": parse_year(payload.get("year") or metadata.get("year") or metadata.get("citation_publication_date")),
        "doi": doi,
        "url": source_url,
        "abstract": clean_extension_text(payload.get("abstract") or metadata.get("abstract") or metadata.get("description"), 10000),
        "pdfCandidates": pdf_candidates,
        "rawMetadata": metadata,
    }


def relative_candidate_url(base_url: str, candidate_url: str) -> str:
    candidate = clean_extension_text(candidate_url, 2000)
    if not candidate:
        return ""
    return urljoin(base_url or "", candidate)


def is_public_http_url(value: str) -> bool:
    parsed = urlparse(value or "")
    if parsed.scheme not in {"http", "https"}:
        return False
    hostname = (parsed.hostname or "").lower()
    if not hostname or hostname == "localhost":
        return False
    try:
        address = ipaddress.ip_address(hostname)
        if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast:
            return False
    except ValueError:
        pass
    return True


def fetch_pdf_candidate(url: str) -> tuple[bytes | None, str]:
    if not is_public_http_url(url):
        return None, "unsupported_url"
    request = Request(
        url,
        headers={
            "Accept": "application/pdf,*/*;q=0.8",
            "User-Agent": "bunken-extension/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(request, timeout=20) as response:
            content_type = (response.headers.get("content-type") or "").split(";", maxsplit=1)[0].strip().lower()
            content_length = int(response.headers.get("content-length") or "0")
            if content_length and content_length > MAX_EXTENSION_PDF_BYTES:
                return None, "too_large"
            chunks = []
            total = 0
            while True:
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_EXTENSION_PDF_BYTES:
                    return None, "too_large"
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data.startswith(b"%PDF") and content_type != "application/pdf":
                return None, "not_pdf"
            return data, "ok"
    except Exception as error:
        return None, f"fetch_failed: {error}"


def storage_upload(path: str, body: bytes, content_type: str, context: dict[str, str]) -> None:
    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is required for Storage upload")
    auth = supabase_request_auth(context)
    api_key = auth["api_key"] or SUPABASE_PUBLIC_KEY or SUPABASE_ADMIN_KEY
    bearer_token = auth["bearer_token"] or (SUPABASE_ADMIN_KEY if SUPABASE_ADMIN_KEY.startswith("eyJ") else "")
    url = f"{SUPABASE_URL}/storage/v1/object/{PDF_STORAGE_BUCKET}/{quote(path, safe='/')}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {bearer_token or api_key}",
        "Content-Type": content_type,
        "x-upsert": "false",
    }
    request = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=30) as response:
            response.read()
    except HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Storage upload failed: {error.code} {error_body}") from error


def make_extension_pdf_storage_path(user_id: str, item_id: str, source_url: str) -> str:
    parsed = urlparse(source_url or "")
    filename = Path(unquote(parsed.path or "paper.pdf")).name or "paper.pdf"
    filename = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "paper.pdf"
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    return f"{user_id}/pdfs/{int(time.time())}-{item_id[:8]}-{filename[:120]}"

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


def build_auth_diagnostics(req) -> dict:
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


def extract_bearer_token(req) -> str:
    custom_token = (req.headers.get("x-bunken-access-token") or "").strip()
    if is_supabase_access_token(custom_token):
        return custom_token

    auth_header = req.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        if is_supabase_access_token(token):
            return token
    return ""


def extract_header_context(req) -> dict[str, str]:
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


def refresh_access_token(refresh_token: str) -> dict:
    normalized_token = clean_extension_text(refresh_token, 4000)
    if not use_supabase():
        raise RuntimeError("SUPABASE_URL and SUPABASE_PUBLIC_KEY are required for token refresh")
    if not normalized_token:
        raise PermissionError("refreshToken is required")
    return request_supabase(
        "/auth/v1/token",
        method="POST",
        query_params={"grant_type": "refresh_token"},
        json_body={"refresh_token": normalized_token},
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


def resolve_request_context(req) -> dict[str, str]:
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


def fetch_reference_ids_for_tag(context: dict[str, str], tag_name: str) -> set[str]:
    normalized = (tag_name or "").strip()
    if not normalized or not use_supabase():
        return set()
    user_id = context.get("userId", "")
    auth = supabase_request_auth(context)
    tags = request_supabase(
        "/rest/v1/tags",
        query_params={"select": "id", "user_id": f"eq.{user_id}", "name": f"ilike.*{normalized}*"},
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    tag_ids = [str(row["id"]) for row in tags or [] if row.get("id")]
    if not tag_ids:
        return set()
    tag_csv = ",".join(tag_ids)
    paper_tags = request_supabase(
        "/rest/v1/paper_tags",
        query_params={"select": "paper_id", "tag_id": f"in.({tag_csv})"},
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    item_tags = request_supabase(
        "/rest/v1/item_tags",
        query_params={"select": "item_id", "tag_id": f"in.({tag_csv})"},
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    ids = {str(row.get("paper_id")) for row in paper_tags or [] if row.get("paper_id")}
    ids.update(str(row.get("item_id")) for row in item_tags or [] if row.get("item_id"))
    return ids


def fetch_reference_ids_for_collection(context: dict[str, str], collection_name: str) -> set[str]:
    normalized = (collection_name or "").strip()
    if not normalized or not use_supabase():
        return set()
    user_id = context.get("userId", "")
    auth = supabase_request_auth(context)
    collections = request_supabase(
        "/rest/v1/collections",
        query_params={"select": "id", "user_id": f"eq.{user_id}", "name": f"ilike.*{normalized}*"},
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    collection_ids = [str(row["id"]) for row in collections or [] if row.get("id")]
    if not collection_ids:
        return set()
    collection_csv = ",".join(collection_ids)
    paper_links = request_supabase(
        "/rest/v1/collection_papers",
        query_params={"select": "paper_id", "collection_id": f"in.({collection_csv})"},
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    item_links = request_supabase(
        "/rest/v1/collection_items",
        query_params={"select": "item_id", "collection_id": f"in.({collection_csv})"},
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    ids = {str(row.get("paper_id")) for row in paper_links or [] if row.get("paper_id")}
    ids.update(str(row.get("item_id")) for row in item_links or [] if row.get("item_id"))
    return ids


def search_user_papers(
    context: dict[str, str],
    query: str,
    tag: str = "",
    collection: str = "",
) -> list[PaperSummary]:
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
            or_parts = [
                f"title.ilike.*{escaped_query}*",
                f"authors.ilike.*{escaped_query}*",
                f"journal.ilike.*{escaped_query}*",
                f"doi.ilike.*{escaped_query}*",
            ]
            if normalized_query.isdigit():
                or_parts.append(f"year.eq.{normalized_query}")
            params["or"] = f"({','.join(or_parts)})"
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
        allowed_ids = None
        if tag:
            allowed_ids = fetch_reference_ids_for_tag(context, tag)
        if collection:
            collection_ids = fetch_reference_ids_for_collection(context, collection)
            allowed_ids = collection_ids if allowed_ids is None else allowed_ids & collection_ids
        if allowed_ids is not None:
            rows = [row for row in rows if str(row.get("id")) in allowed_ids]
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



def find_existing_extension_item(context: dict[str, str], source: dict) -> dict | None:
    if not use_supabase():
        return None
    user_id = context.get("userId", "")
    auth = supabase_request_auth(context)
    doi = source.get("doi") or ""
    for doi_value in doi_lookup_values(doi):
        rows = request_supabase(
            "/rest/v1/paper_items_view",
            query_params={
                "select": EXTENSION_PAPER_SELECT_COLUMNS,
                "user_id": f"eq.{user_id}",
                "doi": f"ilike.{doi_value}",
                "limit": "1",
            },
            bearer_token=auth["bearer_token"],
            api_key=auth["api_key"],
        )
        if rows:
            return rows[0]

    title_key = normalize_title_key(source.get("title"))
    if not title_key:
        return None
    params = {
        "select": EXTENSION_PAPER_SELECT_COLUMNS,
        "user_id": f"eq.{user_id}",
        "title": f"ilike.{source.get('title')}",
        "limit": "5",
    }
    if source.get("year"):
        params["year"] = f"eq.{source['year']}"
    rows = request_supabase(
        "/rest/v1/paper_items_view",
        query_params=params,
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
    )
    for row in rows or []:
        if normalize_title_key(row.get("title")) == title_key:
            return row
    return None


def get_next_extension_display_order(context: dict[str, str]) -> int:
    user_id = context.get("userId", "")
    auth = supabase_request_auth(context)
    try:
        rows = request_supabase(
            "/rest/v1/paper_items_view",
            query_params={
                "select": "display_order",
                "user_id": f"eq.{user_id}",
                "order": "display_order.desc.nullslast",
                "limit": "1",
            },
            bearer_token=auth["bearer_token"],
            api_key=auth["api_key"],
        )
    except Exception:
        return 1
    if not rows:
        return 1
    try:
        return int(rows[0].get("display_order") or 0) + 1
    except (TypeError, ValueError):
        return 1


def create_extension_item(context: dict[str, str], source: dict) -> dict:
    user_id = context.get("userId", "")
    auth = supabase_request_auth(context)
    display_order = get_next_extension_display_order(context)
    payload = {
        "user_id": user_id,
        "item_type": "journalArticle",
        "title": source.get("title") or "Untitled paper",
        "publication_title": source.get("journal") or "",
        "year": source.get("year"),
        "doi": source.get("doi") or None,
        "url": source.get("url") or None,
        "abstract_note": source.get("abstract") or None,
        "extra": {
            "created_by": "chrome_extension",
            "source_url": source.get("url") or "",
            "pdf_candidates": source.get("pdfCandidates") or [],
            "legacy_display_order": str(display_order),
        },
    }
    for field in ("volume", "issue", "pages", "publisher"):
        if source.get(field):
            payload[field] = source[field]
    rows = request_supabase(
        "/rest/v1/items",
        method="POST",
        json_body=payload,
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
        prefer="return=representation",
    )
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("Item insert did not return a row")
    item = rows[0]
    creator_rows = [
        {
            "item_id": item["id"],
            "creator_type": "author",
            "literal_name": author,
            "position": index,
        }
        for index, author in enumerate(source.get("authors") or [], start=1)
    ]
    if creator_rows:
        request_supabase(
            "/rest/v1/creators",
            method="POST",
            json_body=creator_rows,
            bearer_token=auth["bearer_token"],
            api_key=auth["api_key"],
            prefer="return=minimal",
        )
    return item


def create_extension_attachment(context: dict[str, str], item_id: str, storage_path: str, pdf_url: str) -> None:
    user_id = context.get("userId", "")
    auth = supabase_request_auth(context)
    request_supabase(
        "/rest/v1/attachments",
        method="POST",
        json_body={
            "item_id": item_id,
            "user_id": user_id,
            "kind": "pdf",
            "storage_path": storage_path,
            "filename": Path(urlparse(pdf_url).path).name or "paper.pdf",
            "content_type": "application/pdf",
            "title": "PDF from Chrome extension",
        },
        bearer_token=auth["bearer_token"],
        api_key=auth["api_key"],
        prefer="return=minimal",
    )


def save_extension_paper(context: dict[str, str], payload: dict) -> dict:
    if not use_supabase():
        raise RuntimeError("Supabase is required for Chrome extension saves")
    if not context.get("userId") or not context.get("access_token"):
        raise PermissionError("Authentication required")

    source = extension_source_from_payload(payload)
    if source.get("doi"):
        source = merge_extension_metadata(source, fetch_crossref_metadata(source["doi"]))
    if not source.get("title") and not source.get("doi"):
        raise ValueError("title or DOI is required")

    candidates = [relative_candidate_url(source.get("url", ""), value) for value in source.get("pdfCandidates") or []]
    candidates = [value for index, value in enumerate(candidates) if value and value not in candidates[:index]]
    source["pdfCandidates"] = candidates

    existing = find_existing_extension_item(context, source)
    item = existing or create_extension_item(context, source)
    item_id = str(item.get("item_id") or item.get("id") or "")

    pdf_result = {"saved": False, "storagePath": "", "sourceUrl": "", "reason": "no_candidate"}
    if item_id and not existing:
        for candidate in candidates[:5]:
            pdf_bytes, reason = fetch_pdf_candidate(candidate)
            if not pdf_bytes:
                pdf_result = {"saved": False, "storagePath": "", "sourceUrl": candidate, "reason": reason}
                continue
            storage_path = make_extension_pdf_storage_path(context["userId"], item_id, candidate)
            storage_upload(storage_path, pdf_bytes, "application/pdf", context)
            create_extension_attachment(context, item_id, storage_path, candidate)
            pdf_result = {"saved": True, "storagePath": storage_path, "sourceUrl": candidate, "reason": "ok"}
            break

    return {
        "saved": not bool(existing),
        "duplicate": bool(existing),
        "itemId": item_id,
        "paperId": str(item.get("id") or ""),
        "title": item.get("title") or source.get("title") or "",
        "doi": item.get("doi") or source.get("doi") or "",
        "pdfCandidates": candidates,
        "pdf": pdf_result,
    }

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
