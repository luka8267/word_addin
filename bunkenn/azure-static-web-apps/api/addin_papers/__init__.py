import json

import azure.functions as func

from shared.data_access import resolve_request_context, search_user_papers


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        query = req.params.get("q", "")
        papers = search_user_papers(resolve_request_context(req), query)
        return func.HttpResponse(
            json.dumps({"items": [paper.to_dict() for paper in papers]}),
            mimetype="application/json",
            status_code=200,
        )
    except Exception as error:
        status_code = 401 if isinstance(error, PermissionError) else 500
        return func.HttpResponse(
            json.dumps({"error": str(error)}),
            mimetype="application/json",
            status_code=status_code,
        )
