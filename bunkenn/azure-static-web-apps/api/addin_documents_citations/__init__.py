import json

import azure.functions as func

from shared.data_access import list_document_citations, resolve_request_context


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        result = list_document_citations(
            resolve_request_context(req),
            req.params.get("wordDocumentId", ""),
        )
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
