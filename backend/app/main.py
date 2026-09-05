import logging
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth.router import router as auth_router
from app.api.users.router import router as users_router
from app.api.conversations.router import router as conversations_router
from app.api.chat.router import router as chat_router
from app.api.documents.router import router as documents_router
from app.api.mcp import router as mcp_router
from app.ai.embeddings.factory import get_embedding_provider
from app.ai.llm.factory import llm_factory
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
app = FastAPI(title=settings.app_name, version="0.1.0", docs_url="/docs" if settings.environment != "production" else None)
cors_origins = list(dict.fromkeys(
    origin.strip().rstrip("/")
    for origin in [settings.frontend_url, *settings.cors_origins.split(",")]
    if origin.strip()
))
app.add_middleware(CORSMiddleware, allow_origins=cors_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id, started = request.headers.get("X-Request-ID", str(uuid4())), time.perf_counter()
    try: response = await call_next(request)
    except Exception:
        logging.exception("request_failed request_id=%s path=%s", request_id, request.url.path)
        if settings.app_debug: raise
        return JSONResponse(status_code=500, content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}})
    response.headers["X-Request-ID"] = request_id
    logging.info("request request_id=%s method=%s path=%s status=%s duration_ms=%.1f", request_id, request.method, request.url.path, response.status_code, (time.perf_counter()-started)*1000)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"success": False, "error": {"code": "VALIDATION_ERROR", "message": "Request validation failed", "details": exc.errors()}})


@app.get("/api/health", tags=["Health"])
async def health(): return {"status": "healthy", "service": "agentforge-api", "version": "0.1.0"}

@app.get("/api/health/llm", tags=["Health"])
async def llm_health():
    provider=llm_factory.get_provider(settings.default_llm_provider);result=await provider.health_check();return {"provider":settings.default_llm_provider,**result}

@app.get("/api/health/embeddings",tags=["Health"])
async def embedding_health():
    provider=get_embedding_provider();return {"provider":settings.default_embedding_provider,"model":settings.default_embedding_model,"dimension":provider.dimension,"status":"available"}

app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(conversations_router,prefix="/api")
app.include_router(chat_router,prefix="/api")
app.include_router(documents_router,prefix="/api")
app.include_router(mcp_router,prefix="/api")
