import json

import azure.functions as func

from shared.data_access import resolve_user_id


def main(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(
            {
                "userId": str(resolve_user_id()),
                "email": "",
                "username": "cloud-user",
            }
        ),
        mimetype="application/json",
        status_code=200,
    )
