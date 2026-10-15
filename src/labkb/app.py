import hmac
import ipaddress
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from labkb.config import Settings
from labkb.providers import ProviderError
from labkb.schemas import ChatRequest, SearchRequest
from labkb.service import KnowledgeBase
from labkb.store import IndexMismatch


class BodyLimitMiddleware:
    """Enforce limits while receiving, including requests without Content-Length."""

    def __init__(self, app, limit):
        self.app, self.limit = app, limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            consumed += len(message.get("body", b""))
            if consumed > self.limit:
                raise HTTPException(413, "请求超过文件大小限制")
            return message

        await self.app(scope, limited_receive, send)


def create_app(settings=None, provider=None):
    config = settings or Settings.from_env()
    kb = KnowledgeBase(config, provider)
    app = FastAPI(
        title="研知 LabKB",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )
    app.state.kb = kb
    app.add_middleware(BodyLimitMiddleware, limit=config.max_upload_bytes + 64 * 1024)
    if not config.api_token:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]", "testserver"]
        )

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            if not config.api_token:
                try:
                    local_client = (
                        request.client and ipaddress.ip_address(request.client.host).is_loopback
                    )
                except ValueError:
                    local_client = False
                if not local_client:
                    return JSONResponse({"detail": "非本机访问必须配置访问令牌"}, status_code=403)
            if config.api_token:
                supplied = request.headers.get("authorization", "")
                if not hmac.compare_digest(
                    supplied.encode(), f"Bearer {config.api_token}".encode()
                ):
                    return JSONResponse(
                        {"detail": "需要有效访问令牌"},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
            origin = request.headers.get("origin")
            if origin:
                parsed = urlsplit(origin)
                if (
                    parsed.netloc != request.headers.get("host")
                    or parsed.scheme != request.url.scheme
                ):
                    return JSONResponse({"detail": "不允许跨站请求"}, status_code=403)
            length = request.headers.get("content-length")
            if length and (
                not length.isdigit() or int(length) > config.max_upload_bytes + 64 * 1024
            ):
                return JSONResponse({"detail": "请求过大"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(IndexMismatch)
    async def index_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(ProviderError)
    async def provider_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=503)

    @app.exception_handler(ValueError)
    async def validation_error(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/status")
    def status():
        documents = kb.store.list_documents()
        return {
            "mode": config.mode,
            "model": config.chat_model if config.mode == "ollama" else None,
            "embedding_model": config.embed_model if config.mode == "ollama" else None,
            "documents": len(documents),
            "chunks": sum(d["chunk_count"] for d in documents),
        }

    @app.get("/api/documents")
    def documents():
        return {"documents": kb.store.list_documents()}

    @app.post("/api/documents")
    def upload(file: Annotated[UploadFile, File()]):
        try:
            data = file.file.read(config.max_upload_bytes + 1)
            if len(data) > config.max_upload_bytes:
                raise HTTPException(413, "文件超过 10 MiB 限制")
            return kb.ingest(file.filename or "", data)
        finally:
            file.file.close()

    @app.delete("/api/documents/{document_id}")
    def delete(document_id: str):
        with kb.lock:
            if not kb.store.delete(document_id):
                raise HTTPException(404, "文档不存在")
        return {"deleted": True}

    @app.post("/api/demo/seed")
    def seed():
        if config.mode != "demo":
            raise HTTPException(409, "示例按钮仅用于 demo；真实模式请通过上传显式导入资料")
        records = [
            kb.ingest(path.name, path.read_bytes())["document"]
            for path in sorted((Path(__file__).parent / "samples").glob("*.md"))
        ]
        return {"documents": records}

    @app.post("/api/search")
    def search(request: SearchRequest):
        return {"hits": kb.search(request.query, request.top_k)}

    @app.post("/api/chat")
    def chat(request: ChatRequest):
        return kb.chat(request)

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static, check_dir=False), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(static / "index.html")

    return app
