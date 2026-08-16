const $ = (id) => document.getElementById(id);

const api = async (url, options = {}) => {
  const headers = options.body instanceof FormData
    ? { ...(options.headers || {}) }
    : { "Content-Type": "application/json", ...(options.headers || {}) };
  const res = await fetch(url, { headers, ...options });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { text }; }
  if (!res.ok) throw new Error(data.detail || data.error || text || res.statusText);
  return data;
};

const toast = (message) => {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 4200);
};

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, ch => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
}[ch]));

const statusLabels = {
  available: "未出库",
  shipped: "已出库待激活",
  activating: "激活中",
  activation_queued: "排队中",
  activated: "已激活",
  activation_failed: "激活失败",
  account_sent: "已发货",
  partially_activated: "部分激活",
  completed: "已完成",
  queued: "排队中",
  retry: "等待重试",
  cancelled: "已取消",
  switching_account: "切换账号",
  verifying_account: "核验账号",
  reauthorizing: "激活前重新授权",
  reauthorization_failed: "重新授权失败",
  opening_codex: "打开 Codex",
  sending: "发送你好",
  waiting_response: "等待回复",
  ws_connect_failed: "WS 连接失败",
  ws_models_failed: "WS 模型目录失败",
  ws_missing_credentials: "WS 缺少凭证",
  ws_auth_failed: "WS 凭证被拒",
  ws_http_error: "WS 握手错误",
  ws_turn_failed: "WS 激活失败",
  ws_no_reply: "WS 无回复文本",
  turn_status_unknown: "发送结果未知",
  dry_run: "模拟模式",
  failed: "失败",
  reauth_required: "需要重新授权",
};

let oauthImportItemId = 0;
let currentInventoryItems = [];
let oauthBatchPollTimer = null;

function badge(status) {
  const value = status || "unknown";
  return '<span class="badge ' + escapeHtml(value) + '">' +
    escapeHtml(statusLabels[value] || value) + "</span>";
}

function bindTabs() {
  document.querySelectorAll(".nav").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".nav").forEach(x => x.classList.remove("active"));
      document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
      btn.classList.add("active");
      $(btn.dataset.tab).classList.add("active");
    });
  });
}

async function loadSummary() {
  const data = await api("/inventory/summary");
  $("eligibleCount").textContent = data.eligible || 0;
  $("shippedCount").textContent = data.by_status?.shipped || 0;
  $("activatedCount").textContent = data.by_status?.activated || 0;
}

function manualOrderId(item, action) {
  return item.reserved_order_id || "manual-" + action + "-" + item.id + "-" + Date.now();
}

async function manualStatus(item, status) {
  const orderId = status === "available" ? "" : manualOrderId(item, status);
  return api("/inventory/manual-status", {
    method: "POST",
    body: JSON.stringify({ inventory_id: item.id, status, order_id: orderId }),
  });
}

async function activateItem(item, btn) {
  const orderId = "manual-activate-" + item.id + "-" + Date.now();
  btn.disabled = true;
  btn.textContent = "加入队列中";
  try {
    const result = await api("/fulfillments/activate-item", {
      method: "POST",
      body: JSON.stringify({ order_id: orderId, inventory_id: item.id }),
    });
    const batch = result.activation_batch || {};
    toast("已进入激活队列，前面还有 " + (batch.ahead_orders ?? 0) + " 单");
  } catch (err) {
    toast("加入激活队列失败：" + err.message);
  } finally {
    await refreshAll();
  }
}

async function deleteInventory(item, btn) {
  const label = "#" + item.id + " " + (item.email || "");
  if (!window.confirm(
    "确定永久删除库存 " + label + "？\n\n" +
    "对应的已完成激活任务和履约明细会一并清理，此操作不能撤销。"
  )) return;

  btn.disabled = true;
  btn.textContent = "删除中";
  try {
    const result = await api("/inventory/" + item.id, { method: "DELETE" });
    toast("已删除库存 #" + result.inventory_id + " " + result.email);
  } catch (err) {
    toast("删除失败：" + err.message);
  } finally {
    await refreshAll();
  }
}
async function refreshOAuth(item, btn) {
  btn.disabled = true;
  btn.textContent = "授权中";
  try {
    const result = await api("/inventory/" + item.id + "/oauth/refresh", {
      method: "POST",
      body: JSON.stringify({ force_reauth: true }),
    });
    if (result.ok && result.action === "reauthorized") {
      toast("已自动完成 OAuth 重新授权：" + (result.email || item.email));
    } else {
      throw new Error(result.message || "OAuth 重新授权未完成");
    }
  } catch (err) {
    toast("OAuth 重新授权失败：" + err.message);
  } finally {
    btn.disabled = false;
    btn.textContent = "重新授权";
    await refreshAll();
  }
}

function chooseOAuthImport(item) {
  oauthImportItemId = item.id;
  $("oauthImportInput").value = "";
  $("oauthImportInput").click();
}

async function loadInventory() {
  const status = $("statusFilter").value;
  const q = encodeURIComponent($("searchInput").value.trim());
  const items = await api("/inventory?status=" + encodeURIComponent(status) + "&q=" + q + "&limit=300");
  currentInventoryItems = items;
  const body = $("inventoryBody");
  body.innerHTML = items.map(item => {
    const oauthText = item.desktop_oauth_ready
      ? "OAuth 完整"
      : "OAuth 缺少：" + (item.desktop_oauth_missing || []).join(", ");
    const valid = escapeHtml(item.validity_status || "unknown") + "<br><small>" +
      (item.eligible ? "合格" : escapeHtml(item.eligible_reason || "")) +
      "</small><br><small>" + escapeHtml(oauthText) + "</small>";
    return "<tr data-id='" + item.id + "'>" +
      "<td><input class='inventory-select' type='checkbox' value='" + item.id + "' aria-label='选择库存 #" + item.id + "'></td>" +
      "<td>" + item.id + "</td>" +
      "<td>" + escapeHtml(item.email) + "</td>" +
      "<td>" + badge(item.status) + "</td>" +
      "<td>" + escapeHtml(item.reserved_order_id) + "</td>" +
      "<td>" + valid + "</td>" +
      "<td>" + (item.reset_count ?? 0) + "</td>" +
      "<td class='actions'>" +
      "<button data-action='ship'>手动出库</button>" +
      "<button data-action='return'>回库</button>" +
      "<button data-action='activate'>加入激活队列</button>" +
      "<button data-action='refresh-oauth'>重新授权</button>" +
      "<button data-action='import-oauth'>更新 JSON</button>" +
      "<button class='danger' data-action='delete'>删除</button></td></tr>";
  }).join("") || "<tr><td colspan='8'>暂无库存</td></tr>";

  body.querySelectorAll(".inventory-select").forEach(box => {
    box.addEventListener("change", updateInventorySelectAllState);
  });
  updateInventorySelectAllState();

  body.querySelectorAll("tr[data-id]").forEach(row => {
    const item = items.find(x => String(x.id) === row.dataset.id);
    row.querySelector("[data-action='ship']").addEventListener("click", async (ev) => {
      ev.currentTarget.disabled = true;
      try { await manualStatus(item, "shipped"); toast("已手动出库"); }
      catch (err) { toast("手动出库失败：" + err.message); }
      finally { await refreshAll(); }
    });
    row.querySelector("[data-action='return']").addEventListener("click", async (ev) => {
      ev.currentTarget.disabled = true;
      try { await manualStatus(item, "available"); toast("已回库"); }
      catch (err) { toast("回库失败：" + err.message); }
      finally { await refreshAll(); }
    });
    row.querySelector("[data-action='activate']").addEventListener(
      "click", ev => activateItem(item, ev.currentTarget)
    );
    row.querySelector("[data-action='refresh-oauth']").addEventListener(
      "click", ev => refreshOAuth(item, ev.currentTarget)
    );
    row.querySelector("[data-action='import-oauth']").addEventListener(
      "click", () => chooseOAuthImport(item)
    );
    row.querySelector("[data-action='delete']").addEventListener(
      "click", ev => deleteInventory(item, ev.currentTarget)
    );
  });
}


function selectedInventoryIds() {
  return [...document.querySelectorAll(".inventory-select:checked")].map(box => Number(box.value)).filter(Boolean);
}

function updateInventorySelectAllState() {
  const boxes = [...document.querySelectorAll(".inventory-select")];
  const checked = boxes.filter(box => box.checked).length;
  const all = boxes.length > 0 && checked === boxes.length;
  ["selectAllInventory", "selectAllInventoryHeader"].forEach(id => {
    const box = $(id);
    if (box) {
      box.checked = all;
      box.indeterminate = checked > 0 && checked < boxes.length;
    }
  });
}

async function cancelOAuthBatch(batchId, button) {
  if (!window.confirm("确认取消 OAuth 批量任务 #" + batchId + "？仅会取消尚未执行的任务。")) return;
  button.disabled = true;
  button.textContent = "取消中";
  try {
    await api("/oauth/refresh-batches/" + batchId, { method: "DELETE" });
    toast("已取消 OAuth 批量任务 #" + batchId);
    await pollOAuthBatch(batchId);
  } catch (err) {
    toast("取消 OAuth 任务失败：" + err.message);
    button.disabled = false;
    button.textContent = "取消任务";
  }
}

async function retryFailedOAuthBatch(batchId, button) {
  button.disabled = true;
  button.textContent = "重试中";
  try {
    const batch = await api("/oauth/refresh-batches/" + batchId + "/retry-failed", { method: "POST" });
    toast("已重新排队失败的 OAuth 项");
    await pollOAuthBatch(batch.id || batchId);
  } catch (err) {
    toast("重试 OAuth 失败项失败：" + err.message);
    button.disabled = false;
    button.textContent = "重试失败项";
  }
}

function bindOAuthBatchActions(batch) {
  const status = $("oauthBatchStatus");
  const cancelButton = status?.querySelector("[data-cancel-oauth-batch]");
  if (cancelButton) cancelButton.onclick = () => cancelOAuthBatch(batch.id, cancelButton);
  const retryButton = status?.querySelector("[data-retry-oauth-batch]");
  if (retryButton) retryButton.onclick = () => retryFailedOAuthBatch(batch.id, retryButton);
}

async function pollOAuthBatch(batchId) {
  if (oauthBatchPollTimer) clearInterval(oauthBatchPollTimer);
  const render = async () => {
    try {
      const batch = await api("/oauth/refresh-batches/" + batchId);
      const jobs = batch.jobs || [];
      const done = jobs.filter(job => ["succeeded", "failed", "cancelled"].includes(job.status)).length;
      const failed = jobs.filter(job => job.status === "failed");
      const canCancel = ["queued", "running"].includes(batch.status);
      const canRetry = ["failed", "partial_failed"].includes(batch.status) && failed.length > 0;
      const actions = (canCancel ? "<button class='button secondary oauth-batch-action' data-cancel-oauth-batch='" + batch.id + "'>取消任务</button>" : "") +
        (canRetry ? "<button class='button secondary oauth-batch-action' data-retry-oauth-batch='" + batch.id + "'>重试失败项</button>" : "");
      $("oauthBatchStatus").innerHTML =
        "OAuth 批量任务 #" + batch.id + "：" + escapeHtml(batch.status) +
        "，进度 " + done + "/" + jobs.length +
        (failed.length ? "，失败 " + failed.length + " 条" : "") +
        (failed[0]?.last_error ? "<pre class='error-text'>" + escapeHtml(failed[0].last_error) + "</pre>" : "") +
        (actions ? "<div class='oauth-batch-actions'>" + actions + "</div>" : "");
      bindOAuthBatchActions(batch);
      if (["completed", "failed", "partial_failed", "cancelled"].includes(batch.status)) {
        clearInterval(oauthBatchPollTimer);
        oauthBatchPollTimer = null;
        await refreshAll();
      }
    } catch (err) {
      clearInterval(oauthBatchPollTimer);
      oauthBatchPollTimer = null;
      toast("读取 OAuth 批量进度失败：" + err.message);
    }
  };
  await render();
  oauthBatchPollTimer = setInterval(render, 1200);
}

async function startOAuthBatch(ids, label) {
  try {
    const batch = await api("/oauth/refresh-batches", {
      method: "POST",
      body: JSON.stringify({ inventory_ids: ids || [] }),
    });
    toast(label + "已创建，浏览器授权按单并发执行");
    await pollOAuthBatch(batch.id);
  } catch (err) {
    toast(label + "失败：" + err.message);
  }
}

async function loadFulfillments() {
  const list = await api("/fulfillments?limit=30");
  const box = $("fulfillmentList");
  if (!list.length) {
    box.innerHTML = "<div class='fulfillment'>暂无履约记录</div>";
    return;
  }
  const details = await Promise.all(list.slice(0, 10).map(row =>
    api("/fulfillments/" + encodeURIComponent(row.order_id)).catch(() => row)
  ));
  box.innerHTML = details.map(row => {
    const batch = row.activation_batch || {};
    return "<article class='fulfillment'><header><strong>" +
      escapeHtml(row.order_id) + "</strong>" + badge(row.status) + "</header>" +
      "<div>买家：" + escapeHtml(row.buyer_id || "") + "，份数：" + (row.quantity || 1) + "</div>" +
      (batch.id ? "<div>激活批次 #" + batch.id + "：" + badge(batch.status) +
        "，前面还有 " + (batch.ahead_orders ?? 0) + " 单</div>" : "") +
      (row.items || []).map(item => "<div class='item-row'><span>#" +
        item.inventory_id + " " + escapeHtml(item.email || "") + "</span>" +
        "<span>" + badge(item.status) + "</span></div>").join("") +
      (row.last_error ? "<pre class='error-text'>" + escapeHtml(row.last_error) + "</pre>" : "") +
      "<details><summary>发货语句</summary><pre>" +
      escapeHtml(row.delivery_text || "") + "</pre></details></article>";
  }).join("");
}

async function cancelQueuedBatch(batch, button) {
  if (!window.confirm(
    "确认取消批次 #" + batch.id + "？仅会移出尚未开始的激活任务，库存不会自动回库。"
  )) return;
  button.disabled = true;
  button.textContent = "取消中";
  try {
    await api("/activation/queue/" + batch.id, { method: "DELETE" });
    toast("已取消激活批次 #" + batch.id);
    await refreshAll();
  } catch (err) {
    toast("取消失败：" + err.message);
    button.disabled = false;
    button.textContent = "取消排队";
  }
}

async function loadQueue() {
  const [queue, worker] = await Promise.all([
    api("/activation/queue?limit=100"),
    api("/activation/worker/status"),
  ]);
  $("queueCount").textContent = worker.pending_orders || 0;
  $("workerStatus").textContent = worker.running
    ? (worker.leader ? "激活 Worker 运行中" : "Worker 等待接管")
    : "激活 Worker 未运行";
  const box = $("activationQueue");
  box.innerHTML = queue.map(batch => {
    const jobs = batch.jobs || [];
    const canCancel = batch.status === "queued" && jobs.every(
      job => ["queued", "retry"].includes(job.status) && !job.started_at
    );
    const jobRows = jobs.map(job =>
      "<div class='queue-job'><span>#" + job.inventory_id + " " +
      escapeHtml(job.email || "") + "</span><span>" + badge(job.status) +
      " <small>" + escapeHtml(statusLabels[job.stage] || job.stage || "") +
      "</small></span></div>"
    ).join("");
    return "<article class='fulfillment queue-batch' data-batch-id='" + batch.id + "'>" +
      "<header><strong>订单 " + escapeHtml(batch.order_id) + "</strong>" +
      badge(batch.status) + "</header>" +
      "<div class='queue-meta'>批次 #" + batch.id + "，前面还有 " +
      (batch.ahead_orders ?? 0) + " 单，当前阶段：" +
      escapeHtml(statusLabels[batch.current_stage] || batch.current_stage || "") + "</div>" +
      jobRows +
      (batch.last_error ? "<pre class='error-text'>" + escapeHtml(batch.last_error) + "</pre>" : "") +
      "<div class='queue-actions'>" +
      (canCancel ? "<button class='danger' data-cancel-batch='" + batch.id + "'>取消排队</button>" :
        "<span class='queue-lock'>" + (batch.status === "activating" ? "正在执行，不能取消" : "") + "</span>") +
      "</div></article>";
  }).join("") || "<div class='fulfillment'>当前没有待处理激活任务</div>";

  box.querySelectorAll("[data-cancel-batch]").forEach(button => {
    const batch = queue.find(item => String(item.id) === button.dataset.cancelBatch);
    button.addEventListener("click", () => cancelQueuedBatch(batch, button));
  });
}

async function loadDesktopStatus() {
  const data = await api("/desktop-instance/status");
  $("desktopInstanceStatus").textContent = data.bound
    ? (data.online ? "已绑定，实例在线，PID " + data.pid : "已绑定，实例未启动")
    : "未绑定：" + (data.error || "");
}

async function loadSettings() {
  const data = await api("/settings");
  $("xianyuBaseUrl").value = data.xianyu_base_url || "";
  $("xianyuEndpoint").value = data.xianyu_send_endpoint || "/internal/accounts/{account_id}/send-message";
  $("xianyuAccountId").value = data.xianyu_account_id || "";
  $("xianyuToken").value = data.xianyu_api_token || "";
  $("activationProvider").value = data.activation_provider || "desktop";
  $("wsBaseUrl").value = data.ws_base_url || "";
  $("wsProxyUrl").value = data.ws_proxy_url || "";
  $("wsModel").value = data.ws_model || "gpt-5.6-luna";
  $("wsOriginator").value = data.ws_originator || "Codex Desktop";
  $("wsClientVersion").value = data.ws_client_version || "0.147.0-alpha.6.6";
  $("wsServiceTier").value = data.ws_service_tier || "priority";
  $("wsReasoningEffort").value = data.ws_reasoning_effort || "medium";
  $("wsInstallationId").value = data.ws_installation_id || "";
  $("wsOpenaiBeta").value = data.ws_openai_beta || "responses_websockets=2026-02-06";
  $("wsToolsJson").value = data.ws_tools_json || "";
  $("wsReconnectLimit").value = data.ws_reconnect_limit || "5";
  $("wsConnectTimeout").value = data.ws_connect_timeout_seconds || "15";
  $("wsTurnTimeout").value = data.ws_turn_timeout_seconds || "180";
  $("desktopInstanceName").value = data.desktop_instance_name || "fixed-desktop-instance";
  $("desktopInstanceId").value = data.desktop_instance_id || "";
  $("desktopProfileDir").value = data.desktop_profile_dir || "";
  $("desktopAppUserDataDir").value = data.desktop_app_user_data_dir || "";
  $("desktopLaunchCommand").value = data.desktop_launch_command || "";
  $("activationWorkerCount").value = data.activation_worker_count || "3";
  $("desktopInstancePool").value = data.desktop_instance_pool || "";
  $("desktopBackgroundMode").checked = ["1", "true", "yes", "on"].includes(String(data.desktop_background_mode || "").toLowerCase());
  $("desktopAllowForegroundFallback").checked = ["1", "true", "yes", "on"].includes(String(data.desktop_allow_foreground_fallback || "").toLowerCase());
  $("codexPrompt").value = "你好";
  $("reauthBeforeActivation").checked = ["1", "true", "yes", "on"].includes(String(data.reauth_before_activation || "").toLowerCase());
  $("deliveryTemplate").value = data.delivery_template || "";
}

async function loadAudit() {
  const list = await api("/audit?limit=80");
  $("auditList").innerHTML = list.map(row => "<div class='audit-item'><strong>" +
    escapeHtml(row.event_type) + "</strong> <span>" + escapeHtml(row.created_at) +
    "</span><div>订单：" + escapeHtml(row.order_id || "") + "，库存：" +
    (row.inventory_id || "") + "</div><pre>" + escapeHtml(row.payload || "{}") +
    "</pre></div>").join("") || "<div class='audit-item'>暂无审计日志</div>";
}

async function refreshAll() {
  await Promise.all([
    loadSummary(), loadInventory(), loadFulfillments(),
    loadQueue(), loadDesktopStatus(), loadAudit(),
  ]);
}

function selectedJsonFiles() {
  const files = [...($("importFiles").files || []), ...($("importDir").files || [])];
  const seen = new Set();
  return files.filter(file => {
    const key = file.name + ":" + file.size + ":" + file.lastModified;
    if (seen.has(key)) return false;
    seen.add(key);
    return file.name.toLowerCase().endsWith(".json");
  });
}

function importSummary(result, includeFiles = false) {
  const parts = [];
  if (includeFiles) {
    parts.push("解析 " + (result.parsed_files || 0) + "/" + (result.files || 0));
  }
  parts.push("新增 " + (result.created || 0));
  parts.push("更新 " + (result.updated || 0));
  parts.push("未变化 " + (result.skipped || 0));
  parts.push("失败 " + (result.failed_files?.length || 0));
  return parts.join("，");
}

function showImportDetails(result, includeFiles = false) {
  const summary = importSummary(result, includeFiles);
  const hint = $("fileImportHint");
  hint.textContent = "最近导入：" + summary;
  const labels = { created: "新增", updated: "更新", skipped: "未变化" };
  hint.title = (result.details || []).map(item =>
    (labels[item.action] || item.action) + " #" + item.inventory_id + " " + item.email
  ).join("\n");
  toast("导入完成：" + summary);
}
function bindActions() {
  $("refreshBtn").addEventListener("click", refreshAll);
  ["selectAllInventory", "selectAllInventoryHeader"].forEach(id => {
    $(id).addEventListener("change", ev => {
      document.querySelectorAll(".inventory-select").forEach(box => { box.checked = ev.target.checked; });
      updateInventorySelectAllState();
    });
  });
  $("refreshSelectedOauthBtn").addEventListener("click", () => {
    const ids = selectedInventoryIds();
    if (!ids.length) return toast("请先选择要更新的库存");
    startOAuthBatch(ids, "选中库存 OAuth 更新");
  });
  $("refreshAllOauthBtn").addEventListener("click", () => startOAuthBatch([], "全部库存 OAuth 更新"));
  $("statusFilter").addEventListener("change", loadInventory);
  $("searchInput").addEventListener("input", () => setTimeout(loadInventory, 120));
  $("auditRefreshBtn").addEventListener("click", loadAudit);
  $("queueRefreshBtn").addEventListener("click", loadQueue);
  $("testDesktopBtn").addEventListener("click", async () => {
    try {
      const data = await api("/desktop-instance/test", { method: "POST" });
      $("desktopInstanceStatus").textContent = data.online ? "实例在线，检测通过" : "已绑定但实例未启动";
      toast(data.online ? "专用实例检测通过" : "实例已绑定，请在 Cockpit 启动当前绑定实例");
    } catch (err) { toast("实例检测失败：" + err.message); }
  });
  $("importFiles").addEventListener("change", () => $("fileImportHint").textContent = "已选择 " + selectedJsonFiles().length + " 个 JSON 文件");
  $("importDir").addEventListener("change", () => $("fileImportHint").textContent = "已选择 " + selectedJsonFiles().length + " 个 JSON 文件");
  $("oauthImportInput").addEventListener("change", async () => {
    const file = $("oauthImportInput").files?.[0];
    const inventoryId = oauthImportItemId;
    if (!file || !inventoryId) return;
    const form = new FormData();
    form.append("file", file, file.name);
    try {
      const result = await api("/inventory/" + inventoryId + "/oauth/import", {
        method: "POST",
        body: form,
      });
      toast("已更新 OAuth 凭证：" + (result.email || "当前库存"));
      await refreshAll();
    } catch (err) {
      toast("更新 JSON 失败：" + err.message);
    } finally {
      oauthImportItemId = 0;
      $("oauthImportInput").value = "";
    }
  });


  $("importBtn").addEventListener("click", async () => {
    try {
      const payload = $("importText").value.trim();
      if (!payload) throw new Error("请粘贴至少一条 JSON 库存");
      const result = await api("/inventory/import-cpa", {
        method: "POST",
        body: JSON.stringify({ payload, sync_cockpit: $("syncCockpit").checked }),
      });
      showImportDetails(result, false);
      await refreshAll();
    } catch (err) { toast("导入失败：" + err.message); }
  });

  $("importFilesBtn").addEventListener("click", async () => {
    const files = selectedJsonFiles();
    if (!files.length) return toast("请先选择 JSON 文件或目录");
    const form = new FormData();
    files.forEach(file => form.append("files", file, file.webkitRelativePath || file.name));
    form.append("sync_cockpit", $("syncCockpit").checked ? "true" : "false");
    try {
      const result = await api("/inventory/import-cpa-files", { method: "POST", body: form });
      showImportDetails(result, true);
      await refreshAll();
    } catch (err) { toast("文件导入失败：" + err.message); }
  });

  $("shipBtn").addEventListener("click", async () => {
    try {
      const body = {
        order_id: $("orderId").value.trim(),
        buyer_id: $("buyerId").value.trim(),
        item_id: $("itemId").value.trim(),
        platform: $("platform").value.trim() || "chatgpt",
        quantity: Number($("quantity").value || 1),
        send_to_xianyu: $("sendToXianyu").checked,
      };
      if (!body.order_id) throw new Error("请填写订单号");
      const result = await api("/fulfillments/ship", {
        method: "POST",
        headers: { "Idempotency-Key": "ui-ship-" + body.order_id },
        body: JSON.stringify(body),
      });
      toast("已出库并发送 " + (result.items?.length || body.quantity) + " 份");
      await refreshAll();
    } catch (err) { toast("发货失败：" + err.message); }
  });

  $("saveSettingsBtn").addEventListener("click", async () => {
    const values = {
      xianyu_base_url: $("xianyuBaseUrl").value.trim(),
      xianyu_send_endpoint: $("xianyuEndpoint").value.trim(),
      xianyu_account_id: $("xianyuAccountId").value.trim(),
      xianyu_api_token: $("xianyuToken").value.trim(),
      activation_provider: $("activationProvider").value,
      ws_base_url: $("wsBaseUrl").value.trim(),
      ws_proxy_url: $("wsProxyUrl").value.trim(),
      ws_model: $("wsModel").value.trim(),
      ws_originator: $("wsOriginator").value.trim(),
      ws_client_version: $("wsClientVersion").value.trim(),
      ws_service_tier: $("wsServiceTier").value.trim(),
      ws_reasoning_effort: $("wsReasoningEffort").value.trim(),
      ws_installation_id: $("wsInstallationId").value.trim(),
      ws_openai_beta: $("wsOpenaiBeta").value.trim(),
      ws_tools_json: $("wsToolsJson").value.trim(),
      ws_reconnect_limit: $("wsReconnectLimit").value || "5",
      ws_connect_timeout_seconds: $("wsConnectTimeout").value || "15",
      ws_turn_timeout_seconds: $("wsTurnTimeout").value || "180",
      desktop_instance_name: $("desktopInstanceName").value.trim(),
      desktop_instance_id: $("desktopInstanceId").value.trim(),
      desktop_profile_dir: $("desktopProfileDir").value.trim(),
      desktop_app_user_data_dir: $("desktopAppUserDataDir").value.trim(),
      desktop_launch_command: $("desktopLaunchCommand").value.trim(),
      activation_worker_count: $("activationWorkerCount").value || "3",
      desktop_instance_pool: $("desktopInstancePool").value.trim(),
      desktop_background_mode: $("desktopBackgroundMode").checked ? "true" : "false",
      desktop_allow_foreground_fallback: $("desktopAllowForegroundFallback").checked ? "true" : "false",
      codex_prompt: "你好",
      reauth_before_activation: $("reauthBeforeActivation").checked ? "true" : "false",
      delivery_template: $("deliveryTemplate").value,
    };
    try {
      await api("/settings", { method: "PUT", body: JSON.stringify({ values }) });
      toast("绑定设置已保存");
      await loadSettings();
      await loadDesktopStatus();
    } catch (err) { toast("保存失败：" + err.message); }
  });

  $("previewBtn").addEventListener("click", async () => {
    await api("/settings", { method: "PUT", body: JSON.stringify({ values: { delivery_template: $("deliveryTemplate").value } }) });
    const data = await api("/delivery/preview", { method: "POST", body: JSON.stringify({ inventory_ids: [] }) });
    $("templatePreview").textContent = data.text;
  });
}

(async function init() {
  bindTabs();
  bindActions();
  try { await loadSettings(); await refreshAll(); }
  catch (err) { toast("页面初始化失败：" + err.message); }
  setInterval(() => {
    Promise.all([loadSummary(), loadFulfillments(), loadQueue(), loadDesktopStatus()]).catch(() => {});
  }, 3000);
})();
