# API 说明

默认地址为 `http://127.0.0.1:8000`。`/health` 不要求令牌；设置 `LABKB_API_TOKEN` 后，所有 `/api/` 路径要求请求头 `Authorization: Bearer <令牌>`。网页根路径和静态资源仍可访问，但访问资料与操作 API 需要令牌。跨站浏览器请求受到限制。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/health` | 应用进程健康检查，不检查 Ollama |
| GET | `/api/status` | 模式、模型与资料 / 片段数量 |
| GET | `/api/documents` | 列出文档 |
| POST | `/api/documents` | multipart 字段 `file` 上传单个文档 |
| DELETE | `/api/documents/{document_id}` | 删除指定文档及其检索片段 |
| POST | `/api/demo/seed` | 仅 demo：加载仓库自带的虚构示例 |
| POST | `/api/search` | 检索相关片段 |
| POST | `/api/chat` | 带检索的问答 |
| GET | `/api/openapi.json` | 机器可读的 OpenAPI 规范 |

## 检索和问答

检索请求 JSON：

```json
{"query":"仪器应该如何预约？","top_k":4}
```

响应对象中的 `hits` 是片段数组，带有编号、文件名、位置与原文。问答请求 JSON：

```json
{"message":"仪器应该如何预约？","history":[],"top_k":4}
```

`message` / `query` 最多 800 字符；`top_k` 为 1–6，默认 4。`history` 最多 12 条，每条 `role` 为 `user` 或 `assistant`，`content` 最多 3000 字符；实际发送给模型前还会按上下文预算缩减。问题和历史不能作为授予系统指令的通道。

问答响应包含：

- `answer`：回答、直接摘录或拒答文本。
- `citations`：回答引用的来源片段。
- `refused`、`mode`、`warnings`：是否拒答、运行模式和解释性提示。
- `retrieval_ms`、`generation_ms`、`usage`：检索、生成与模型返回的计时数据。demo 的 `usage` 为空。
- `citation_validated`：是否通过本轮引用编号检查；**仅验证编号归属，不代表语义或事实核验通过**。

拒答文本没有足够证据时应视为正常业务结果，不是服务异常。真实模型可能把不相关片段组织成看似合理的答案，仍须人工核对。

## Python 调用示例

从项目根目录运行，`.env` 已配置令牌时会读取它：

```python
import os

import httpx
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("LABKB_API_TOKEN", "")
headers = {"Authorization": f"Bearer {token}"} if token else {}
with httpx.Client(
    base_url="http://127.0.0.1:8000", headers=headers, timeout=300, trust_env=False
) as client:
    response = client.post(
        "/api/chat", json={"message": "新人入组第一周应该做什么？", "history": []}
    )
    response.raise_for_status()
    print(response.json())
```

## 容量与错误

上传支持 TXT、Markdown、带文字层的 PDF、DOCX；单文件最多 10 MiB，最多提取 50 万字符，PDF 最多 300 页，全库最多 5000 个片段。重复文件内容会被去重；同名而内容变化的上传不是自动版本管理，旧文档需按业务需要显式删除。

常见状态码：`401` 令牌缺失或不正确，`403` 跨站请求或无令牌时的非本机访问被拒绝，`404` 文档不存在，`409` 索引配置不一致或当前模式不支持操作，`413` 上传 / 请求过大，`422` 请求字段不符合约束，`503` 模型服务失败。文档解析或其它业务参数错误可能返回 `400`。客户端应展示错误说明，不要在失败后伪装成回答成功。

API 当前为非流式响应，单进程串行保护知识库操作。它适合建立集成与评测入口，不提供 OpenAI 接口兼容性、多租户权限或生产级并发保证。
