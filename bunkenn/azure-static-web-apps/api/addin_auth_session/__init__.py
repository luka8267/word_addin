import json

import azure.functions as func

from shared.data_access import (
    build_auth_diagnostics,
    debug_endpoints_enabled,
    resolve_request_context,
)


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        if req.params.get("_debug") == "env":
            if not debug_endpoints_enabled():
                return func.HttpResponse("Not found", status_code=404)
            return func.HttpResponse(
                json.dumps(build_auth_diagnostics(req)),
                mimetype="application/json",
                status_code=200,
            )
        context = resolve_request_context(req)
        if not context.get("userId"):
            return func.HttpResponse(
                json.dumps({"authenticated": False}),
                mimetype="application/json",
                status_code=200,
            )
        return func.HttpResponse(
            json.dumps(
                {
                    "authenticated": True,
                    "userId": context["userId"],
                    "email": context.get("email", ""),
                    "username": context.get("username", ""),
                }
            ),
            mimetype="application/json",
            status_code=200,
        )
    except Exception as error:
        return func.HttpResponse(
            json.dumps({"authenticated": False, "error": str(error)}),
            mimetype="application/json",
            status_code=401,
        )
