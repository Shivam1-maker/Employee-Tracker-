"""Application entry point."""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.database import init_db
from app.routers import admin_crud, auth, logins, notifications, workforce

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STATIC = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    s = get_settings()
    if s.secret_key.startswith("change-me"):
        logging.getLogger("elt").warning("ELT_SECRET_KEY is the default value. Set a strong secret before deploying.")
    init_db()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title=s.app_name, version="1.0.0", lifespan=lifespan,
                  description="Records employee login events with consent-based location and shift compliance.")

    if s.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.cors_origins.split(",")],
                           allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(self), camera=(), microphone=()"
        if not request.url.path.startswith(("/docs", "/redoc")):
            resp.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    app.include_router(auth.router)
    app.include_router(admin_crud.router)
    app.include_router(logins.router)
    app.include_router(workforce.router)
    app.include_router(notifications.router)

    @app.get("/health", tags=["system"])
    def health():
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse("/static/login.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
