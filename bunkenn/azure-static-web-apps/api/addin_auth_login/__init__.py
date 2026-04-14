import json

import azure.functions as func

from shared.data_access import build_context_from_token, login_with_password


def main(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = req.get_json()
        email = (payload.get("email") or "").strip()
        password = payload.get("password") or ""
        if not email or not password:
            return func.HttpResponse(
                json.dumps({"error": "email and password are required"}),
                mimetype="application/json",
                status_code=400,
            )

        auth_response = login_with_password(email, password)
        access_token = auth_response.get("access_token") or ""
        refresh_token = auth_response.get("refresh_token") or ""
        context = build_context_from_token(access_token)

        return func.HttpResponse(
            json.dumps(
                {
                    "accessToken": access_token,
                    "refreshToken": refresh_token,
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
            json.dumps({"error": str(error)}),
            mimetype="application/json",
            status_code=401,
        )
