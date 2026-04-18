import json
import mimetypes
import os
import sqlite3
import ssl
from dataclasses import asdict, dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


DB_PATH = Path(__file__).with_name("papers.db")
DEFAULT_USER_ID = int(os.getenv("BUNKEN_DEFAULT_USER_ID", "1"))
HOST = os.getenv("BUNKEN_ADDIN_HOST", "127.0.0.1")
PORT = int(os.getenv("BUNKEN_ADDIN_PORT", "8765"))
TLS_CERT = os.getenv("BUNKEN_ADDIN_TLS_CERT", "")
TLS_KEY = os.getenv("BUNKEN_ADDIN_TLS_KEY", "")
STATIC_DIR = Path(
    os.getenv(
        "BUNKEN_ADDIN_STATIC_DIR",
        r"C:\Users\run_r\AppData\Local\Packages\Microsoft.MinecraftUWP_8wekyb3d8bbwe\LocalState\games\com.mojang\development_behavior_packs\bunken-word-addin",
    )
)


@dataclass
class PaperSummary:
    id: str
    title: str
    authors: str
    journal: str
    year: int
    doi: str | None = None


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def resolve_user_id() -> int:
    return DEFAULT_USER_ID


def search_user_papers(user_id: int, query: str) -> list[PaperSummary]:
    normalized_query = f"%{(query or '').strip()}%"
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, title, authors, journal, year
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
            (user_id, normalized_query, normalized_query, normalized_query, normalized_query),
        ).fetchall()
    return [
        PaperSummary(
            id=str(row["id"]),
            title=row["title"] or "",
            authors=row["authors"] or "",
            journal=row["journal"] or "",
            year=int(row["year"] or 0),
        )
        for row in rows
    ]


def fetch_papers_by_ids(user_id: int, paper_ids: list[str]) -> list[PaperSummary]:
    if not paper_ids:
        return []

    placeholders = ",".join("?" for _ in paper_ids)
    params: list[Any] = [user_id, *paper_ids]
    with get_connection() as connection:
        rows = connection.execute(
            f"""
            SELECT id, title, authors, journal, year
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
        )
        for row in rows
    }
    return [by_id[paper_id] for paper_id in paper_ids if paper_id in by_id]


def build_in_text_citation(paper: PaperSummary, style: str, locator: str | None = None) -> str:
    normalized_style = normalize_style(style)
    lead_author = first_author_label(paper.authors)
    if normalized_style in {"vancouver", "acs", "nature", "ieee"}:
        locator_part = f", {locator}" if locator else ""
        return f"[{paper.id}{locator_part}]"

    locator_part = f", {locator}" if locator else ""
    return f"({lead_author}, {paper.year}{locator_part})"


def build_bibliography_entry(paper: PaperSummary, style: str) -> str:
    normalized_style = normalize_style(style)
    if normalized_style == "ieee":
        return f'{paper.authors}, "{paper.title}," {paper.journal}, {paper.year}.'
    if normalized_style == "acs":
        return f"{paper.authors}. {paper.title}. {paper.journal} {paper.year}."
    if normalized_style == "vancouver":
        return f"{paper.authors}. {paper.title}. {paper.journal}. {paper.year}."
    if normalized_style == "nature":
        return f"{paper.authors} {paper.title}. {paper.journal} ({paper.year})."
    return f"{paper.authors} ({paper.year}). {paper.title}. {paper.journal}."


def normalize_style(style: str) -> str:
    normalized = (style or "").strip().lower()
    if normalized in {"vancouver", "apa", "acs", "nature", "ieee"}:
        return normalized
    return "vancouver"


def first_author_label(authors: str) -> str:
    parts = [part.strip() for part in (authors or "").split(",") if part.strip()]
    return parts[0] if parts else "Unknown"


class AddinApiHandler(BaseHTTPRequestHandler):
    server_version = "BunkenAddinAPI/0.1"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        print(f"GET {parsed.path}", flush=True)
        if parsed.path == "/api/addin/papers":
            query = parse_qs(parsed.query).get("q", [""])[0]
            papers = search_user_papers(resolve_user_id(), query)
            self.write_json({"items": [asdict(paper) for paper in papers]})
            return

        if self.serve_static(parsed.path):
            return

        self.write_json({"error": {"message": "not found"}}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        print(f"POST {parsed.path}", flush=True)
        payload = self.read_json_body()

        if parsed.path == "/api/addin/auth/session":
            self.write_json(
                {
                    "userId": str(resolve_user_id()),
                    "email": "",
                    "username": "local-user",
                }
            )
            return

        if parsed.path == "/api/addin/citations/format":
            items = payload.get("items", [])
            style = payload.get("style", "vancouver")
            paper_ids = [str(item.get("paperId")) for item in items]
            papers = fetch_papers_by_ids(resolve_user_id(), paper_ids)
            rendered_items = []
            for item, paper in zip(items, papers):
                text = build_in_text_citation(
                    paper,
                    style=style,
                    locator=item.get("locator"),
                )
                rendered_items.append(
                    {
                        "paperId": paper.id,
                        "renderedText": text,
                    }
                )
            self.write_json(
                {
                    "text": "; ".join(item["renderedText"] for item in rendered_items),
                    "items": rendered_items,
                }
            )
            return

        if parsed.path == "/api/addin/bibliography/format":
            style = payload.get("style", "vancouver")
            paper_ids = [str(paper_id) for paper_id in payload.get("paperIds", [])]
            unique_ids = list(dict.fromkeys(paper_ids))
            papers = fetch_papers_by_ids(resolve_user_id(), unique_ids)
            self.write_json(
                {
                    "title": "References",
                    "entries": [build_bibliography_entry(paper, style) for paper in papers],
                }
            )
            return

        if self.serve_static(parsed.path):
            return

        self.write_json({"error": {"message": "not found"}}, status=HTTPStatus.NOT_FOUND)

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length) if length else b"{}"
        if not raw_body:
            return {}
        return json.loads(raw_body.decode("utf-8"))

    def write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_common_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_common_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def serve_static(self, raw_path: str) -> bool:
        relative_path = raw_path.lstrip("/") or "taskpane.html"
        if relative_path in {"", "."}:
            relative_path = "taskpane.html"

        candidate = (STATIC_DIR / relative_path).resolve()
        static_root = STATIC_DIR.resolve()
        print(f"STATIC root={static_root} candidate={candidate}", flush=True)

        if not str(candidate).startswith(str(static_root)):
            print("STATIC reject prefix", flush=True)
            return False
        if not candidate.exists() or not candidate.is_file():
            print("STATIC missing", flush=True)
            return False

        content_type, _ = mimetypes.guess_type(str(candidate))
        data = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_common_headers()
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
        return True


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), AddinApiHandler)
    scheme = "http"
    if TLS_CERT and TLS_KEY:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(TLS_CERT, TLS_KEY)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        scheme = "https"
    print(f"bunken add-in API listening on {scheme}://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
