import json

import azure.functions as func

from shared.data_access import resolve_user_id, search_user_papers


def main(req: func.HttpRequest) -> func.HttpResponse:
    query = req.params.get("q", "")
    papers = search_user_papers(resolve_user_id(), query)
    return func.HttpResponse(
        json.dumps({"items": [paper.to_dict() for paper in papers]}),
        mimetype="application/json",
        status_code=200,
    )
