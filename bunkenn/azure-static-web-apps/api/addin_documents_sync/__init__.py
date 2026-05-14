import json

import azure.functions as func

from shared.data_access import resolve_request_context, sync_document_citations


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = req.get_json()
        result = sync_document_citations(resolve_request_context(req), payload)
        return func.HttpResponse(
            json.dumps(result),
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
