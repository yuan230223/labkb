import math
import re
from collections import Counter

STOP_WORDS = {"the", "is", "a", "an", "of", "to", "and", "what", "how", "do", "in", "for"}
ZH_STOP = {
    "什么",
    "怎么",
    "如何",
    "哪些",
    "可以",
    "需要",
    "一下",
    "我们",
    "这个",
    "那个",
    "是否",
    "多少",
    "时候",
    "哪里",
    "请问",
}


def tokenize(text: str) -> list[str]:
    result = [w for w in re.findall(r"[a-z0-9_]+", text.lower()) if w not in STOP_WORDS]
    for run in re.findall(r"[\u3400-\u9fff]+", text):
        result.extend(run[i : i + 2] for i in range(len(run) - 1) if run[i : i + 2] not in ZH_STOP)
    return result


def cosine(a, b):
    if not a or not b or len(a) != len(b):
        raise ValueError("向量维度不一致，请重建索引")
    denominator = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / denominator if denominator else 0.0


def rank(chunks, query, query_vector=None, top_k=4, threshold=0.55):
    if not chunks:
        return []
    query_tokens = set(tokenize(query))
    counts = [Counter(tokenize(c["text"])) for c in chunks]
    lengths = [sum(c.values()) for c in counts]
    average = sum(lengths) / len(lengths) or 1
    frequencies = Counter(token for count in counts for token in count)
    lexical = []
    semantic = []
    for i, (chunk, count) in enumerate(zip(chunks, counts, strict=True)):
        score = 0.0
        overlap = query_tokens.intersection(count)
        for token in overlap:
            tf = count[token]
            idf = math.log(
                1 + (len(chunks) - frequencies[token] + 0.5) / (frequencies[token] + 0.5)
            )
            score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * lengths[i] / average))
        # Weak keyword overlap is not enough evidence by itself.
        required = 1 if len(query_tokens) <= 2 else max(2, math.ceil(len(query_tokens) * 0.25))
        if score and len(overlap) >= required:
            lexical.append((i, score))
        if query_vector is not None and chunk["vector"] is not None:
            similarity = cosine(query_vector, chunk["vector"])
            if similarity >= threshold:
                semantic.append((i, similarity))
    fused = Counter()
    for ranking in (lexical, semantic):
        for position, (idx, _) in enumerate(
            sorted(ranking, key=lambda item: item[1], reverse=True)[:40], 1
        ):
            fused[idx] += 1 / (60 + position)
    hits = []
    for idx, score in fused.most_common(top_k):
        chunk = chunks[idx]
        hits.append(
            {
                "id": len(hits) + 1,
                "document_id": chunk["document_id"],
                "document_name": chunk["document_name"],
                "location": chunk["location"],
                "text": chunk["text"],
                "score": round(score, 6),
            }
        )
    return hits
