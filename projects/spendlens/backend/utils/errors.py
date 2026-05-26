from __future__ import annotations

import traceback
from typing import Any

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException


def json_ok(payload: dict[str, Any], status: int = 200):
    # Keep response shape stable for frontend.
    return jsonify({"success": True, "data": payload}), status


def json_error(app: Flask, message: str, status: int = 400, *, detail: str | None = None):
    body: dict[str, Any] = {"success": False, "error": message}
    if detail:
        body["detail"] = detail if app.debug else detail.splitlines()[-1]
    app.logger.error("API error %s: %s %s", status, message, request.path)
    if detail and app.debug:
        # Helpful for dev only.
        print(traceback.format_exc())
    return jsonify(body), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        if request.path.startswith("/api/"):
            return json_error(app, exc.description or str(exc), exc.code or 400)
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        if request.path.startswith("/api/"):
            return json_error(app, str(exc), 500, detail=traceback.format_exc())
        # Non-API errors should still crash loudly so we notice them.
        raise exc

