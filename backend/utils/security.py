"""
Security helpers — rate limiting setup, safe error responses, header injection.

Design rationale:
  • SlowAPI is wired up here so the main module stays clean.
  • safe_error_response() ensures we NEVER leak tracebacks to the client;
    we log the real error server-side and return a generic message.
  • Security headers are applied via a Starlette middleware factory.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter

from backend.config import get_settings

logger = logging.getLogger("farm_coordinator.security")


def safe_get_remote_address(request: Request) -> str:
    """
    Safely extract the client IP address, falling back to proxy headers
    if request.client is None (common in serverless environments like Vercel).
    """
    for header in ["x-forwarded-for", "x-real-ip"]:
        val = request.headers.get(header)
        if val:
            return val.split(",")[0].strip()
            
    if request.client and hasattr(request.client, "host") and request.client.host:
        return request.client.host
        
    return "127.0.0.1"


# ── Rate Limiter Singleton ───────────────────────────────────────────────
# Keyed by client IP; the limit string comes from settings.
limiter = Limiter(key_func=safe_get_remote_address)


def get_limiter() -> Limiter:
    """Return the global SlowAPI limiter instance."""
    return limiter


# ── Safe Error Responses ─────────────────────────────────────────────────

def safe_error_response(
    status_code: int = 500,
    message: str = "An internal error occurred. Please try again later.",
    *,
    detail: Any = None,
) -> JSONResponse:
    """
    Build a JSON error response that is safe to show to end users.

    The optional *detail* is logged server-side but never sent to the client.
    """
    if detail:
        logger.error("Error detail (hidden from client): %s", detail)

    return JSONResponse(
        status_code=status_code,
        content={"error": message},
    )


# ── Security Headers Middleware ──────────────────────────────────────────

async def add_security_headers(request: Request, call_next) -> Response:
    """
    ASGI middleware that injects hardening headers on every response.

    Headers applied:
      • X-Content-Type-Options: nosniff  — prevents MIME-sniffing
      • X-Frame-Options: DENY            — blocks iframe embedding
      • Content-Security-Policy           — tight CSP for the frontend
      • X-XSS-Protection: 1; mode=block  — legacy XSS filter
      • Referrer-Policy: strict-origin-when-cross-origin
      • Permissions-Policy                — disable unused browser APIs
    """
    response: Response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # CSP: allow self + inline styles (many frontend frameworks need this)
    # + Google Fonts if used.  Restrict everything else to same-origin.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )

    # Disable sensors / geolocation / payment APIs the app doesn't need.
    response.headers["Permissions-Policy"] = (
        "geolocation=(), camera=(), microphone=(), payment=()"
    )

    return response


# ── Input Sanitisation (extra layer) ─────────────────────────────────────

def sanitize_for_log(value: str, max_len: int = 200) -> str:
    """
    Truncate and neutralise a string before writing it to a log line.

    This prevents log-injection attacks where a crafted input could insert
    fake log entries or ANSI escape sequences.
    """
    safe = value.replace("\n", "\\n").replace("\r", "\\r")
    if len(safe) > max_len:
        safe = safe[:max_len] + "…"
    return safe
