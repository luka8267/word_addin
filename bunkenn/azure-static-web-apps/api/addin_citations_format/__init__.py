import json

import azure.functions as func

from shared.bunken_service import build_in_text_citation
from shared.data_access import fetch_papers_by_ids, resolve_request_context


def main(req: func.HttpRequest) -> func.HttpResponse:
    payload = req.get_json()
    items = payload.get("items", [])
    style = payload.get("style", "apa")
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

    return func.HttpResponse(
        json.dumps(
            {
                "text": "; ".join(item["renderedText"] for item in rendered_items),
                "items": rendered_items,
            }
        ),
        mimetype="application/json",
        status_code=200,
    )
