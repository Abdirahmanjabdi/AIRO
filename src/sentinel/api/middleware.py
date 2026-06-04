"""
Sentinel-Zero — Custom Middleware
==================================
Request ID injection for correlation and structured logging.

Ref: AI_CONTRACT.md §1.3 (circuit-breaker logging with correlation IDs)
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Injects a unique X-Request-ID header into every request/response.
    Logs request method, path, status, and latency.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        # Attach to request state for downstream access
        request.state.request_id = request_id

        response: Response = await call_next(request)

        elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "[%s] %s %s → %d (%.2fms)",
            request_id[:8],
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )

        return response
