import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


@dataclass(frozen=True)
class Settings:
    mode: str = "demo"
    data_dir: Path = Path("data")
    ollama_url: str = "http://127.0.0.1:11434"
    chat_model: str = "qwen3:8b"
    embed_model: str = "qwen3-embedding:0.6b"
    api_token: str = ""
    num_ctx: int = 8192
    max_upload_bytes: int = 10 * 1024 * 1024
    max_text_chars: int = 500_000
    max_chunks: int = 5000
    chunk_size: int = 650
    chunk_overlap: int = 100
    semantic_threshold: float = 0.55

    def __post_init__(self):
        if self.mode not in {"demo", "ollama"}:
            raise ValueError("LABKB_MODE 必须是 demo 或 ollama")
        if self.num_ctx < 4096:
            raise ValueError("LABKB_NUM_CTX 至少为 4096")
        if not 0 <= self.chunk_overlap < self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        url = urlparse(self.ollama_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username:
            raise ValueError("LABKB_OLLAMA_URL 必须是无内嵌凭据的 HTTP(S) 地址")
        if self.api_token and len(self.api_token) < 24:
            raise ValueError("LABKB_API_TOKEN 至少为 24 个字符")

    @classmethod
    def from_env(cls):
        return cls(
            mode=os.getenv("LABKB_MODE", "demo"),
            data_dir=Path(os.getenv("LABKB_DATA_DIR", "data")),
            ollama_url=os.getenv("LABKB_OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            chat_model=os.getenv("LABKB_CHAT_MODEL", "qwen3:8b"),
            embed_model=os.getenv("LABKB_EMBED_MODEL", "qwen3-embedding:0.6b"),
            api_token=os.getenv("LABKB_API_TOKEN", ""),
            num_ctx=int(os.getenv("LABKB_NUM_CTX", "8192")),
            semantic_threshold=float(os.getenv("LABKB_SEMANTIC_THRESHOLD", "0.55")),
        )

    def check_bind(self, host: str):
        if host not in {"127.0.0.1", "::1", "localhost"} and not self.api_token:
            raise ValueError("局域网监听必须设置至少 24 字符的 LABKB_API_TOKEN")
