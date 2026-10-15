# v0.1 本地验收记录

验收日期：2026-10-15（Asia/Shanghai）。这是软件原型的功能记录，不是硬件采购结论。

## 已验证

- Windows 11、Python 3.12.14，项目虚拟环境安装成功，`pip check` 无依赖冲突。
- `pytest -q`：14 项通过。覆盖文档去重、删除与重启、中文检索、未知问题、历史边界、令牌与跨站限制、非本机访问、流式超限上传、DOCX 表格、空白 PDF、向量维度与模型指纹、失败回滚、引用编号和提示预算。
- `ruff check .` 与 `node --check src/labkb/static/app.js` 通过。
- 浏览器实测：加载 2 份虚构资料 / 10 个片段，提问“实验数据需要如何命名和备份？”，显示 2 条引用和原文；未发现浏览器控制台错误。
- 实际 HTTP 评测运行 `examples/eval.jsonl` 的 6 个案例，错误数 0，来源 Recall@4 为 1.0，拒答标记匹配率为 1.0。题库极小且是人工编写的功能演示，不能推出真实语料或模型的准确率。
- 本次演示端口为 8765；标准 CLI 默认端口为 8000。

原始评测结果位于本地 `data/benchmark.json`，截图位于 `artifacts/labkb-preview.jpg`，这两个目录不提交 Git。demo 没有调用模型，生成 token/s 为 `null`；这里不把毫秒级的摘录响应时间当作 LLM 速度。

测试环境有一条 Starlette 关于未来测试客户端切换的弃用提示，目前测试正常通过。依赖快照见 `requirements.lock`；真实环境升级依赖后需重跑测试。

## 未验证与边界

- 未安装和运行真实 Ollama 模型；已用模拟 HTTP 检查 `/api/tags`、`/api/embed` 和 `/api/chat` 请求协议及故障行为。
- 未测真实 GPU 吞吐、显存、内存峰值、多用户并发及实际组内回答质量。
- 此电脑未提供 Docker 命令，容器构建与运行尚未验证；CI 配置尚未在 GitHub 远端运行。
- PDF / DOCX 解析尚未放入隔离子进程；解压和文本大小限制不等同于完整的恶意文件防护。
- 已进行独立代码审查，并修复无令牌远端访问、PDF 累计解压限制、写入侧向量维度一致性问题。

## 复跑

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
node --check src/labkb/static/app.js
# 先启动服务、加载示例资料，再运行：
.\.venv\Scripts\python.exe scripts/benchmark.py --base-url http://127.0.0.1:8765
```
