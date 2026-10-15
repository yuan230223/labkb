# 部署指南

## 本机原生运行

先按 README 创建虚拟环境和 `.env`，从项目根目录运行 `python -m labkb`。默认访问地址是 `http://127.0.0.1:8000`，仅本机可以连接。

Ollama 与 LabKB 是两个进程。前者负责加载模型和推理，后者负责资料解析、检索和网页/API。Ollama 的安装与 GPU 支持以[官方安装入口](https://ollama.com/download)及[官方 GPU 文档](https://docs.ollama.com/gpu)为准。

如需明确禁止 Ollama 使用云能力，在 Ollama 服务的运行环境设置 `OLLAMA_NO_CLOUD=1` 并重启该服务。这不是 LabKB 的变量；仅写入 LabKB 的 `.env` 不会改变另一个已经运行的 Ollama 进程。[Ollama 本地模式说明](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)

## Docker：先验证 demo

需要已经安装且启动的 Docker Engine / Docker Desktop。容器监听 `0.0.0.0`，因此即使宿主机只发布回环端口，也必须设置至少 24 字符的令牌。

先复制 `.env.example` 为 `.env`，保持 `LABKB_MODE=demo`。在终端生成随机令牌，将输出填入 `.env` 的 `LABKB_API_TOKEN`，不要将 `.env` 提交到 Git：

```text
python -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up --build -d
docker compose logs -f labkb
```

打开 `http://127.0.0.1:8000`，在界面中填入同一个访问令牌。Compose 默认仅发布宿主机 `127.0.0.1:8000`，并将命名卷 `labkb_data` 挂载到容器 `/app/data`。停止容器使用 `docker compose down`，命名卷保留；不要在没有备份时使用删除卷的选项。

镜像不包含模型或组内文档。`.dockerignore` 排除本地资料、数据库、令牌和开发环境。Docker 配置提供部署路径；是否在你的 Docker 与操作系统组合上正常工作，需要实际构建和验证。

## Docker 连接宿主机 Ollama

Compose 内固定将 Ollama 地址设为 `http://host.docker.internal:11434`，并配置 `extra_hosts: host.docker.internal:host-gateway`。容器内的 `127.0.0.1` 指容器自身，不能用它访问宿主机上的 Ollama。

1. 先在宿主机安装 Ollama，下载 README 中的两个模型。
2. 确保 Ollama 监听的地址可以被 Docker 访问。Ollama 默认只监听回环地址；必要时按官方说明设置 `OLLAMA_HOST`，只放行受控的 Docker 网络和本机，不向公网开放 `11434`。[监听配置说明](https://docs.ollama.com/faq#how-can-i-expose-ollama-on-my-network)
3. 将 `.env` 中 `LABKB_MODE` 改为 `ollama`。如果命名卷中已导入 demo 数据，先在界面删除这些示例文档，再用真实模式重新导入；也可使用独立的 Compose 项目名称创建隔离的数据卷。
4. 执行 `docker compose up -d --force-recreate`，检查日志并上传小型测试文档。

本 Compose 只容器化 LabKB，GPU 由宿主机 Ollama 管理。如需将 Ollama 也放进容器，按[官方容器指南](https://docs.ollama.com/docker)配置 GPU 支持，并自行验证驱动与运行时；这不在当前 Compose 中。

## 组内局域网试用

先在 `.env` 设置随机 `LABKB_API_TOKEN`，再运行：

```text
python -m labkb --host 0.0.0.0 --port 8000
```

使用服务器在组内网络的 IP 连接。所有持有令牌的人共享同一资料空间；当前没有只读用户或按文档授权。只导入适合向整个试用组公开的资料。跨不可信网络部署时需要 HTTPS、网络访问控制、身份系统与相应测试，不能把开发服务直接暴露到公网。

Compose 仍默认绑定宿主机回环；若确定需要局域网访问，应明确修改端口映射并同步配置防火墙和 HTTPS。更改应用监听地址不会自动修改 Docker 的端口发布范围。

## 数据和升级

原生运行数据保存在 `LABKB_DATA_DIR`，容器数据保存在挂载卷。停服后备份整个数据目录，再进行升级或索引迁移。索引包含从原始资料提取的内容，应按原始资料的保密级别保存；删除网页中的文档不等于清除了外部备份。

保持单个应用进程；不要增加 Uvicorn workers 或启动多个实例共享同一个数据目录。当前导入、检索和生成串行受保护，部署多个实例需要额外的并发协调设计。`GET /health` 仅表示应用进程可响应，不证明 Ollama 已连接、模型已下载或索引与配置一致。

改变嵌入模型或从 demo 切换到 ollama 后，需要重新导入资料构建对应索引。不要仅改模型名称就把旧向量当成新向量使用。聊天模型可以独立比较，但每次评测都应记录模型和参数。

## 常见问题

| 现象 | 检查顺序 |
| --- | --- |
| 返回访问未授权 | 界面令牌与服务环境变量是否一致；重启后是否仍为同一值 |
| 容器拒绝启动 | 令牌是否缺失或不足 24 字符；查看 `docker compose logs labkb` |
| 连不上 Ollama | 服务是否运行；地址是否可达；容器是否错误指向自身；监听与防火墙是否匹配 |
| 模型不存在 | 执行 `ollama list`，确认聊天模型和嵌入模型都已下载 |
| PDF 没有文字 | 文档是否为扫描件；先用受控的 OCR 流程处理 |
| 资料中有答案却拒答 | 查看分块是否正确、问题关键词、索引模式和模型；加入失败案例重新评测 |
| 生成很慢 | 查看 `ollama ps` 的 CPU/GPU 分配，区分模型加载、检索、提示处理与生成耗时 |
| 多轮问题不连贯 | 检查历史长度和指代，复现为固定的多轮题目；不要仅通过增加窗口处理 |

`ollama ps` 可以查看模型的内存分配与 GPU/CPU 情况；上下文与并行请求会影响内存需求。[Ollama FAQ](https://docs.ollama.com/faq)
