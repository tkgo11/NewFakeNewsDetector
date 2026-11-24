import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .catalog import Catalog
from .engine import Engine, configured_catalog
from .google import GoogleFactChecks
from .models import CheckRequest, CheckResult

WEB_ROOT = Path(__file__).parent / "web"
CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
)


def json_only(request: Request) -> None:
    media_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise HTTPException(415, "Use application/json.")


def create_app(catalog: Catalog | None = None, transport: httpx.BaseTransport | None = None):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        key = os.environ.get("GOOGLE_FACTCHECK_API_KEY", "").strip()
        with httpx.Client(
            timeout=httpx.Timeout(5, connect=2),
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
            transport=transport,
            trust_env=False,
        ) as client:
            app.state.engine = Engine(
                catalog or configured_catalog(),
                GoogleFactChecks(key, client) if key else None,
            )
            yield

    app = FastAPI(
        title="NewFakeNewsDetector",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.middleware("http")
    async def response_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(WEB_ROOT / "index.html")

    @app.get("/api/v1/config")
    async def config(request: Request) -> dict[str, bool]:
        return {"online_available": request.app.state.engine.provider is not None}

    @app.post("/api/v1/check", dependencies=[Depends(json_only)])
    def check(payload: CheckRequest, request: Request) -> CheckResult:
        return request.app.state.engine.check(payload)

    app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")
    return app
