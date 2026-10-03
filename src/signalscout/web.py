"""FastAPI application entry point."""

from pathlib import Path
import logging
import hashlib

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .intelligence import make_router as make_intelligence_router
from .config import Settings
from .database import make_engine, make_session_factory
from .logging_setup import configure_logging
from .monitoring import make_router as make_monitoring_router
from .feed import make_router as make_feed_router
from .collection import make_router as make_collection_router


API_PREFIX = "/api"
STATIC_DIR = Path(__file__).parent / "static"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging()
    logger.info("Web process starting")
    app = FastAPI(title="SignalScout", docs_url=None, redoc_url=None)
    engine = make_engine(settings)
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    app.state.ready_logged = False

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        logger.error("Unhandled request error")
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    @app.middleware("http")
    async def same_origin_mutations(request: Request, call_next):
        if request.method in MUTATING_METHODS:
            origin = request.headers.get("origin")
            fetch_site = request.headers.get("sec-fetch-site")
            expected = f"{request.url.scheme}://{request.headers.get('host', '')}"
            if (
                (origin is None and fetch_site != "same-origin")
                or (origin is not None and origin != expected)
                or fetch_site not in {None, "same-origin"}
            ):
                return JSONResponse({"detail": "Cross-origin request forbidden"}, status_code=403)
        return await call_next(request)

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1"])

    @app.get("/", include_in_schema=False)
    def index():
        page = (STATIC_DIR / "index.html").read_text()
        for script in ('app.js', 'agent_workspace.js', 'intelligence.js'):
            version = hashlib.sha256((STATIC_DIR / script).read_bytes()).hexdigest()[:12]
            page = page.replace(f'src="/{script}"', f'src="/{script}?v={version}"')
        return HTMLResponse(page, headers={"Cache-Control": "no-store"})

    @app.get("/app.js", include_in_schema=False)
    def app_script():
        return FileResponse(STATIC_DIR / "app.js", media_type="text/javascript",
                            headers={"Cache-Control": "no-store"})

    @app.get('/intelligence.js', include_in_schema=False)
    def intelligence_script():
        return FileResponse(STATIC_DIR / 'intelligence.js', media_type='text/javascript',
                            headers={'Cache-Control':'no-store'})

    @app.get('/agent_workspace.js', include_in_schema=False)
    def workspace_script():
        return FileResponse(STATIC_DIR / 'agent_workspace.js', media_type='text/javascript', headers={'Cache-Control':'no-store'})

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health")
    def health():
        try:
            with app.state.session_factory() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError:
            return JSONResponse({"detail": "Database unavailable"}, status_code=503)
        if not app.state.ready_logged:
            logger.info("Web ready")
            app.state.ready_logged = True
        return {"status": "ok"}

    api.include_router(make_monitoring_router(app.state.session_factory))
    api.include_router(make_feed_router(app.state.session_factory))
    api.include_router(make_collection_router(app.state.session_factory))
    api.include_router(make_intelligence_router(engine))
    app.include_router(api)
    return app
