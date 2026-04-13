import json

import azure.functions as func

from shared.bunken_service import build_bibliography_entry
from shared.data_access import fetch_papers_by_ids, resolve_user_id


def main(req: func.HttpRequest) -> func.HttpResponse:
    payload = req.get_json()
    style = payload.get("style", "apa")
    paper_ids = [str(paper_id) for paper_id in payload.get("paperIds", [])]
    unique_ids = list(dict.fromkeys(paper_ids))
    papers = fetch_papers_by_ids(resolve_user_id(), unique_ids)
    response = {
        "title": "References" if style in {"apa", "nature"} else "Bibliography",
        "entries": [build_bibliography_entry(paper, style) for paper in papers],
    }
    return func.HttpResponse(
        json.dumps(response),
        mimetype="application/json",
        status_code=200,
    )
