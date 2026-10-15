import math

import httpx

from labkb.store import IndexMismatch


class ProviderError(RuntimeError):
    pass


class OllamaProvider:
    def __init__(self, settings):
        self.settings = settings

    def request(self, path, payload=None):
        try:
            with httpx.Client(
                base_url=self.settings.ollama_url, timeout=180, trust_env=False
            ) as client:
                response = client.get(path) if payload is None else client.post(path, json=payload)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderError(
                "Ollama 请求失败；请检查服务、模型是否已下载及内存占用（未切换为演示答案）"
            ) from exc

    def fingerprint(self):
        data = self.request("/api/tags")
        model = next(
            (
                m
                for m in data.get("models", [])
                if m.get("name") == self.settings.embed_model
                or m.get("model") == self.settings.embed_model
            ),
            None,
        )
        if not model or not model.get("digest"):
            raise ProviderError("未找到 embedding 模型，请先 ollama pull 配置中的完整模型标签")
        return f"{self.settings.embed_model}:{model['digest']}"

    def embed(self, texts, query=False):
        if query and self.settings.embed_model.startswith("qwen3-embedding"):
            texts = [
                "Instruct: Given a question, retrieve relevant passages that answer it\nQuery: " + t
                for t in texts
            ]
        vectors = []
        dimension = None
        for start in range(0, len(texts), 16):
            batch = texts[start : start + 16]
            data = self.request(
                "/api/embed",
                {"model": self.settings.embed_model, "input": batch, "truncate": False},
            )
            result = data.get("embeddings")
            if not isinstance(result, list) or len(result) != len(batch):
                raise ProviderError("Ollama 返回的向量数量不匹配")
            for vector in result:
                if (
                    not isinstance(vector, list)
                    or not vector
                    or any(not isinstance(x, (float, int)) or not math.isfinite(x) for x in vector)
                    or not any(vector)
                ):
                    raise ProviderError("Ollama 返回无效向量")
                dimension = dimension or len(vector)
                if len(vector) != dimension:
                    raise ProviderError("Ollama 返回的向量维度不一致")
            vectors.extend(result)
        return vectors

    def chat(self, messages):
        data = self.request(
            "/api/chat",
            {
                "model": self.settings.chat_model,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {"temperature": 0, "num_ctx": self.settings.num_ctx, "num_predict": 512},
            },
        )
        answer = data.get("message", {}).get("content", "").strip()
        if not answer:
            raise ProviderError("模型未返回正文，请检查模型是否支持 think=false")
        usage = {
            key: data.get(key)
            for key in ("eval_count", "eval_duration", "prompt_eval_count", "load_duration")
        }
        usage["tokens_per_second"] = (
            round(data["eval_count"] * 1e9 / data["eval_duration"], 2)
            if data.get("eval_duration") and data.get("eval_count")
            else None
        )
        return answer, usage


def index_fingerprint(settings, provider):
    identity = provider.fingerprint() if settings.mode == "ollama" else "demo-lexical"
    return f"schema1|chunks:{settings.chunk_size}:{settings.chunk_overlap}|{identity}"


def ensure_same(before, settings, provider):
    if before != index_fingerprint(settings, provider):
        raise IndexMismatch("embedding 模型在操作期间变化，请重试并重建索引")
