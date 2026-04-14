import json

import azure.functions as func

from shared.data_access import resolve_user_profile


def main(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(resolve_user_profile()),
        mimetype="application/json",
        status_code=200,
    )
