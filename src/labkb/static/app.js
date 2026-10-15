"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const state = { history: [], sending: false, mutating: false, documents: [], token: "", mode: null };
  const tokenKey = "labkb-api-token";
  let notificationTimer;

  try { state.token = sessionStorage.getItem(tokenKey) || ""; } catch (_) { /* Storage may be disabled. */ }
  $("api-token").value = state.token;

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = String(content);
    return node;
  }

  function notify(message, success = false) {
    clearTimeout(notificationTimer);
    const notice = $("notification");
    notice.textContent = message;
    notice.className = success ? "notification success" : "notification";
    notice.hidden = false;
    if (success) notificationTimer = setTimeout(() => { notice.hidden = true; }, 6500);
  }

  function readableDetail(detail) {
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) return detail.map((item) => typeof item === "string" ? item : item.msg || "请求参数有误").join("；");
    if (detail && typeof detail.message === "string") return detail.message;
    return null;
  }

  async function api(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (state.token) headers.set("Authorization", `Bearer ${state.token}`);
    let response;
    try { response = await fetch(path, { ...options, headers, credentials: "same-origin" }); }
    catch (_) { throw new Error("无法连接知识库服务，请检查服务是否启动后重试。"); }
    if (response.status === 204) return {};
    let data = {};
    try { data = await response.json(); } catch (_) {
      if (response.ok) throw new Error("服务返回的内容格式不正确，请检查服务状态。");
    }
    if (!response.ok) {
      if (response.status === 401) {
        $("connection-settings").open = true;
        throw new Error("访问未获授权。请在左侧「连接设置」中填写正确的访问令牌。");
      }
      throw new Error(readableDetail(data.detail) || readableDetail(data.error) || `请求未成功（HTTP ${response.status}），请稍后重试。`);
    }
    return data;
  }

  function setConnected(connected) {
    $("connection-state").className = `connection-state ${connected ? "connected" : "disconnected"}`;
    $("connection-label").textContent = connected ? "服务已连接" : "服务未连接";
  }

  function renderStatus(status) {
    state.mode = status.mode;
    const demo = status.mode === "demo";
    $("seed-button").hidden = !demo;
    $("documents-empty").textContent = demo
      ? "还没有资料。上传一份文档，或先体验示例知识库。"
      : "还没有资料。上传组内文档后，即可开始提问。";
    setConnected(true);
    $("mode-banner").className = "mode-banner";
    $("mode-title").textContent = demo ? "演示模式 · 文档检索" : "本地模型模式";
    $("mode-description").textContent = demo
      ? "按关键词检索并展示原文摘录，不调用大模型，也不代表大模型问答效果。"
      : "检索资料后，由配置的本地模型回答；请结合引用原文核实内容。";
    $("mode-badge").textContent = demo ? "DEMO" : "LOCAL MODEL";
    $("runtime-model").textContent = demo ? "关键词检索 · 未调用大模型" : `模型：${status.model || "未指定"}`;
    $("runtime-embedding").textContent = demo ? "本地资料摘录演示" : `嵌入模型：${status.embedding_model || "未指定"}`;
    $("stat-documents").textContent = Number.isFinite(status.documents) ? status.documents : state.documents.length;
    $("stat-chunks").textContent = Number.isFinite(status.chunks) ? status.chunks : "—";
  }

  function fileType(name) {
    const extension = String(name).split(".").pop().toLowerCase();
    return ({ markdown: "MD", docx: "DOC" })[extension] || extension.slice(0, 4) || "TXT";
  }

  function renderDocuments(documents) {
    state.documents = Array.isArray(documents) ? documents : [];
    $("document-list").replaceChildren();
    $("document-count").textContent = state.documents.length;
    $("documents-empty").hidden = state.documents.length > 0;
    state.documents.forEach((doc) => {
      const item = element("li", "document-item");
      item.append(element("span", "document-icon", fileType(doc.name)));
      const info = element("div", "document-info");
      const name = element("span", "document-name", doc.name);
      name.title = doc.name;
      info.append(name, element("span", "document-meta", `${doc.chunk_count ?? 0} 个检索片段`));
      const remove = element("button", "delete-document", "×");
      remove.type = "button";
      remove.title = `删除 ${doc.name}`;
      remove.setAttribute("aria-label", `删除文档 ${doc.name}`);
      remove.disabled = state.mutating;
      remove.addEventListener("click", () => deleteDocument(doc));
      item.append(info, remove);
      $("document-list").append(item);
    });
  }

  async function refresh() {
    const results = await Promise.allSettled([api("/api/status"), api("/api/documents")]);
    if (results[1].status === "fulfilled") renderDocuments(results[1].value.documents);
    if (results[0].status === "fulfilled") {
      renderStatus(results[0].value);
    } else {
      setConnected(false);
      $("seed-button").hidden = true;
      $("mode-banner").className = "mode-banner offline";
      $("mode-title").textContent = "暂时无法读取运行状态";
      $("mode-description").textContent = "请确认服务已启动；配置了访问令牌时，请在连接设置中填写。";
      $("mode-badge").textContent = "OFFLINE";
      $("runtime-model").textContent = "运行状态未知";
      $("runtime-embedding").textContent = "等待重新连接";
    }
    const failure = results.find((result) => result.status === "rejected");
    if (failure) notify(failure.reason.message);
    return !failure;
  }

  function setMutationBusy(busy, message = "") {
    state.mutating = busy;
    $("upload-button").disabled = busy;
    $("seed-button").disabled = busy;
    $("upload-progress").hidden = !busy;
    $("upload-progress").textContent = message;
    document.querySelectorAll(".delete-document").forEach((button) => { button.disabled = busy; });
  }

  async function upload(file) {
    if (!file || state.mutating) return;
    if (!/\.(txt|md|pdf|docx)$/i.test(file.name)) {
      notify("支持 .txt、.md、.pdf 和 .docx 文件，请选择其中一种格式。");
      return;
    }
    setMutationBusy(true, `正在解析并入库：${file.name}…`);
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await api("/api/documents", { method: "POST", body });
      const refreshed = await refresh();
      if (refreshed) notify(result.duplicate ? "这份资料已经在知识库中，无需重复上传。" : `「${file.name}」已加入知识库。`, true);
    } catch (error) { notify(error.message); }
    finally { setMutationBusy(false); $("document-file").value = ""; }
  }

  async function deleteDocument(doc) {
    if (state.mutating || !window.confirm(`从知识库中删除「${doc.name}」及其检索片段？\n已显示的历史回答会保留。`)) return;
    setMutationBusy(true, "正在删除文档…");
    try {
      await api(`/api/documents/${encodeURIComponent(doc.id)}`, { method: "DELETE" });
      if (await refresh()) notify(`「${doc.name}」已从知识库删除。`, true);
    } catch (error) { notify(error.message); }
    finally { setMutationBusy(false); }
  }

  function sourceCard(citation) {
    const card = element("article", "source-card");
    const heading = element("div", "source-heading");
    heading.append(element("span", "source-number", citation.id ?? "·"), element("span", "source-name", citation.document_name || "知识库文档"));
    card.append(heading);
    card.append(element("div", "source-location", citation.location || "文档片段"));
    card.append(element("blockquote", "", citation.text || "未提供原文片段"));
    return card;
  }

  function renderSources(citations) {
    const list = $("sources-list");
    list.replaceChildren();
    list.className = citations.length ? "sources-list has-sources" : "sources-list";
    $("source-count").textContent = citations.length;
    if (citations.length) {
      citations.forEach((citation) => list.append(sourceCard(citation)));
    } else {
      const empty = element("div", "sources-empty");
      const icon = element("span", "", "▤");
      icon.setAttribute("aria-hidden", "true");
      empty.append(icon, element("strong", "", "等待相关资料"), element("p", "", "没有可展示的引用。上传资料后，试着把问题说得更具体。"));
      list.append(empty);
    }
  }

  function scrollConversation() { $("conversation").scrollTop = $("conversation").scrollHeight; }

  function createMessage(role, content, extraClass = "") {
    $("welcome").hidden = true;
    const message = element("article", `message ${role} ${extraClass}`.trim());
    const avatar = element("span", "message-avatar", role === "user" ? "你" : "知");
    avatar.setAttribute("aria-hidden", "true");
    const inner = element("div", "message-content");
    inner.append(element("span", "message-label", role === "user" ? "你" : "研知 LabKB"));
    const body = element("p", "message-body", content);
    inner.append(body);
    message.append(avatar, inner);
    $("conversation").append(message);
    scrollConversation();
    return { message, inner, body };
  }

  function setSending(sending) {
    state.sending = sending;
    $("send-button").disabled = sending;
    $("question").disabled = sending;
    $("clear-chat").disabled = sending;
    $("send-button").setAttribute("aria-label", sending ? "正在回答" : "发送问题");
    $("chat-form").setAttribute("aria-busy", String(sending));
    document.querySelectorAll("[data-question]").forEach((button) => { button.disabled = sending; });
  }

  async function sendQuestion() {
    const message = $("question").value.trim();
    if (!message || state.sending) return;
    if (message.length > 800) {
      notify("问题最多 800 字符，请缩短后重试。");
      return;
    }
    $("notification").hidden = true;
    createMessage("user", message);
    $("question").value = "";
    $("question").style.height = "auto";
    setSending(true);
    const pending = createMessage("assistant", "正在检索知识库", "pending");
    const dots = element("span", "pending-dots", "···");
    dots.setAttribute("aria-hidden", "true");
    pending.body.append(dots);
    try {
      const result = await api("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history: state.history.slice(-6).map((item) => ({ role: item.role, content: item.content.slice(0, 3000) })), top_k: 4 }),
      });
      pending.message.classList.remove("pending");
      const answer = typeof result.answer === "string" ? result.answer : "服务未返回有效回答，请重试。";
      pending.body.textContent = answer;
      const citations = Array.isArray(result.citations) ? result.citations : [];
      const meta = element("div", "message-meta");
      meta.append(element("span", "", result.mode === "demo" ? "原文摘录 · 未调用大模型" : "本地模型回答"));
      if (result.refused) meta.append(element("span", "", "资料不足"));
      if (Number.isFinite(result.retrieval_ms)) meta.append(element("span", "", `本次检索 ${Math.round(result.retrieval_ms)} ms`));
      if (citations.length) {
        const view = element("button", "citation-button", `${citations.length} 条引用 ↗`);
        view.type = "button";
        view.addEventListener("click", () => {
          renderSources(citations);
          $("sources-title").setAttribute("tabindex", "-1");
          $("sources-title").focus({ preventScroll: true });
          $("sources-title").scrollIntoView({ behavior: "smooth", block: "nearest" });
        });
        meta.append(view);
        const details = element("details", "message-citations");
        details.append(element("summary", "", "展开引用原文"));
        citations.forEach((citation) => details.append(sourceCard(citation)));
        pending.inner.append(details);
      }
      pending.inner.append(meta);
      if (Array.isArray(result.warnings)) result.warnings.forEach((warning) => {
        if (typeof warning === "string") pending.inner.append(element("p", "message-warning", warning));
      });
      renderSources(citations);
      state.history.push({ role: "user", content: message }, { role: "assistant", content: answer.slice(0, 3000) });
      state.history = state.history.slice(-6);
    } catch (error) {
      pending.message.classList.remove("pending");
      pending.message.classList.add("error");
      pending.body.textContent = `${error.message}\n问题已放回输入框，可以修改后重试。`;
      $("question").value = message;
    } finally {
      setSending(false);
      scrollConversation();
      $("question").focus({ preventScroll: true });
    }
  }

  $("upload-button").addEventListener("click", () => $("document-file").click());
  $("document-file").addEventListener("change", (event) => upload(event.target.files[0]));
  const uploadZone = $("upload-zone");
  ["dragenter", "dragover"].forEach((type) => uploadZone.addEventListener(type, (event) => {
    event.preventDefault();
    if (!state.mutating) uploadZone.classList.add("drag-over");
  }));
  ["dragleave", "drop"].forEach((type) => uploadZone.addEventListener(type, (event) => {
    event.preventDefault();
    uploadZone.classList.remove("drag-over");
  }));
  uploadZone.addEventListener("drop", (event) => {
    if (event.dataTransfer.files.length !== 1) { notify("每次请上传一个文件。"); return; }
    upload(event.dataTransfer.files[0]);
  });
  // Avoid navigating away when a file is dropped outside the upload area.
  window.addEventListener("dragover", (event) => { if (Array.from(event.dataTransfer.types).includes("Files")) event.preventDefault(); });
  window.addEventListener("drop", (event) => { if (event.dataTransfer.files.length) event.preventDefault(); });

  $("seed-button").addEventListener("click", async () => {
    if (state.mutating) return;
    setMutationBusy(true, "正在准备示例资料…");
    try {
      await api("/api/demo/seed", { method: "POST" });
      if (await refresh()) notify("示例资料已就绪。点击示例问题，开始体验。", true);
    } catch (error) { notify(error.message); }
    finally { setMutationBusy(false); }
  });

  $("token-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    state.token = $("api-token").value.trim();
    let storageSaved = true;
    try {
      if (state.token) sessionStorage.setItem(tokenKey, state.token);
      else sessionStorage.removeItem(tokenKey);
    } catch (_) { storageSaved = false; }
    if (await refresh()) notify(storageSaved ? "连接设置已保存，服务已连接。" : "服务已连接。浏览器不允许保存令牌，刷新页面后需要重新填写。", true);
  });

  $("chat-form").addEventListener("submit", (event) => { event.preventDefault(); sendQuestion(); });
  $("question").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
      event.preventDefault();
      sendQuestion();
    }
  });
  $("question").addEventListener("input", () => {
    $("question").style.height = "auto";
    $("question").style.height = `${Math.min($("question").scrollHeight, 150)}px`;
  });
  document.querySelectorAll("[data-question]").forEach((button) => button.addEventListener("click", () => {
    $("question").value = button.dataset.question;
    sendQuestion();
  }));
  $("clear-chat").addEventListener("click", () => {
    if (state.sending) return;
    state.history = [];
    $("conversation").querySelectorAll(".message").forEach((message) => message.remove());
    $("welcome").hidden = false;
    $("question").value = "";
    $("question").style.height = "auto";
    renderSources([]);
    $("notification").hidden = true;
    $("question").focus({ preventScroll: true });
  });

  refresh();
})();
