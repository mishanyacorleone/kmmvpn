import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config import settings

logger = logging.getLogger(__name__)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_log(request: Request, call_next):
    response = await call_next(request)
    if "/admin/" in request.url.path and request.url.path != "/admin/auth/login":
        logger.info(
            "ADMIN | %s %s | status=%d | ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            request.client.host,
        )
    return response


from web.admin.routes import router as admin_router
from web.public.routes import router as public_router

app.include_router(admin_router)
app.include_router(public_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}