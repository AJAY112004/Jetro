from __future__ import annotations

import functools
import os
import time
import uuid
from typing import Any, Callable

import jwt
from flask import Flask, g, request, session, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from jwt import PyJWTError


def _jwt_secret(app: Flask) -> str:
    # For JWT-HS256, prefer a long random secret. Production should always override via env.
    return (
        os.environ.get("JWT_SECRET")
        or app.config.get("SPENDLENS_SECRET")
        or "spendlens-local-dev-key-change-me-to-secure-please"
    )


def _jwt_enabled(app: Flask) -> bool:
    return os.environ.get("AUTH_ENABLED", "1") == "1"


def init_limiter(app: Flask) -> Limiter:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[os.environ.get("RATE_LIMIT_DEFAULT", "60 per minute")],
        app=app,
    )
    return limiter


def init_security_headers(app: Flask) -> None:
    # Helmet-equivalent security headers. Keep CSP permissive to avoid breaking PDF/JS.
    csp = os.environ.get("CSP_POLICY")
    if csp:
        content_security_policy = {"default-src": csp}
    else:
        content_security_policy = None

    Talisman(
        app,
        force_https=False,
        frame_options="DENY",
        content_security_policy=content_security_policy,
        referrer_policy="strict-origin-when-cross-origin",
        session_cookie_secure=bool(int(os.environ.get("SESSION_COOKIE_SECURE", "0"))),
    )


def init_jwt(app: Flask) -> None:
    app.config["JWT_ENABLED"] = _jwt_enabled(app)


def issue_jwt_token(app: Flask, user_id: str, *, expires_in_s: int = 60 * 60 * 24 * 7) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + expires_in_s,
        "iss": "spendlens",
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, _jwt_secret(app), algorithm="HS256")


def verify_jwt_token(app: Flask, token: str) -> dict[str, Any]:
    decoded = jwt.decode(token, _jwt_secret(app), algorithms=["HS256"], options={"require": ["sub", "exp"]})
    return decoded


def require_auth(view_func: Callable):
    @functools.wraps(view_func)
    def _wrapped(*args, **kwargs):
        app = current_app
        if not app.config.get("JWT_ENABLED", False):
            return view_func(*args, **kwargs)

        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return (
                {"success": False, "error": "Missing Authorization: Bearer <token>"},
                401,
            )

        token = auth.split(" ", 1)[1].strip()
        if not token:
            return ({"success": False, "error": "Empty bearer token"}, 401)

        try:
            decoded = verify_jwt_token(app, token)
            g.user_id = decoded.get("sub")
        except PyJWTError:
            return ({"success": False, "error": "Invalid or expired token"}, 401)

        # Issue a stable user id in session as well (used by session-based report cache).
        session.setdefault("user_id", g.user_id)
        return view_func(*args, **kwargs)

    return _wrapped

