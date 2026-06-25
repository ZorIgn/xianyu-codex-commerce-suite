const $ = (id) => document.getElementById(id);

const api = async (url, options = {}) => {
  const headers = options.body instanceof FormData
    ? { ...(options.headers || {}) }
    : { 'Content-Type': 'application/json', ...(options.headers || {}) };
  const res = await fetch(url, { headers, ...options });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { text }; }
  if (!res.ok) throw new Error(data.detail || data.error || text || res.statusText);
  return data;
};

const toast = (msg) => {
  const el = $('toast');
  el.textContent = msg;
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 4200);
};

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[ch]));
}

function bindTabs() {
  document.querySelectorAll('.nav').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.nav').forEach(x => x.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      $(btn.dataset.tab).classList.add('active');
    });
  });
}

function badge(status) {
  const label = {
    available: '未出库',
    shipped: '已出库待激活',
    activated: '已激活',
    activation_failed: '激活失败',
    reserved: '已占用',
    consumed: '已消耗',
    account_sent: '已发货',
    partially_activated: '部分激活',
    failed: '失败',
  }[status] || status;
  return `<span class="badge ${escapeHtml(status)}">${escapeHtml(label)}</span>`;
}

async function loadSummary() {
  const data = await api('/inventory/summary');
  $('eligibleCount').textContent = data.eligible || 0;
  $('shippedCount').textContent = data.by_status?.shipped || 0;
  $('activatedCount').textContent = data.by_status?.activated || 0;
}

function manualOrderId(item, action) {
  return item.reserved_order_id || `manual-${action}-${item.id}-${Date.now()}`;
}

async function manualStatus(item, status) {
  const orderId = status === 'available' ? '' : manualOrderId(item, status);
  await api('/inventory/manual-status', {
    method: 'POST',
    body: JSON.stringify({ inventory_id: item.id, status, order_id: orderId }),
  });
}

async function activateItem(item, btn) {
  const orderId = item.reserved_order_id || manualOrderId(item, 'activate');
  btn.disabled = true;
  btn.textContent = '启动CLI中';
  try {
    const result = await api('/fulfillments/activate-item', {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId, inventory_id: item.id }),
    });
    const reply = result.codex_reply || result.items?.[0]?.activation_reply || '';
    toast(`激活完成，Codex 回复：${reply || 'ok'}`);
  } catch (err) {
    toast(`激活失败：${err.message}`);
  } finally {
    await refreshAll();
  }
}

async function loadInventory() {
  const status = $('statusFilter').value;
  const q = encodeURIComponent($('searchInput').value.trim());
  const items = await api(`/inventory?status=${encodeURIComponent(status)}&q=${q}&limit=300`);
  const body = $('inventoryBody');
  body.innerHTML = items.map(item => {
    const valid = `${escapeHtml(item.validity_status || '')}<br><small>${item.eligible ? '合格' : escapeHtml(item.eligible_reason || '')}</small>`;
    return `<tr data-id="${item.id}">
      <td>${item.id}</td>
      <td>${escapeHtml(item.email || '')}</td>
      <td>${badge(item.status)}</td>
      <td>${escapeHtml(item.reserved_order_id || '')}</td>
      <td>${valid}</td>
      <td>${item.reset_count ?? 0}</td>
      <td class="actions">
        <button data-action="ship">手动出库</button>
        <button data-action="return">回库</button>
        <button data-action="activate">强制激活</button>
      </td>
    </tr>`;
  }).join('') || '<tr><td colspan="7">暂无库存</td></tr>';

  body.querySelectorAll('tr[data-id]').forEach(row => {
    const item = items.find(x => String(x.id) === row.dataset.id);
    row.querySelector('[data-action="ship"]').addEventListener('click', async (ev) => {
      ev.currentTarget.disabled = true;
      try {
        await manualStatus(item, 'shipped');
        toast('已手动出库');
      } catch (err) {
        toast(`手动出库失败：${err.message}`);
      } finally {
        await refreshAll();
      }
    });
    row.querySelector('[data-action="return"]').addEventListener('click', async (ev) => {
      ev.currentTarget.disabled = true;
      try {
        await manualStatus(item, 'available');
        toast('已回库');
      } catch (err) {
        toast(`回库失败：${err.message}`);
      } finally {
        await refreshAll();
      }
    });
    row.querySelector('[data-action="activate"]').addEventListener('click', (ev) => activateItem(item, ev.currentTarget));
  });
}

async function loadFulfillments() {
  const list = await api('/fulfillments?limit=30');
  const box = $('fulfillmentList');
  if (!list.length) {
    box.innerHTML = '<div class="fulfillment">暂无履约记录</div>';
    return;
  }
  const details = await Promise.all(list.slice(0, 10).map(row => api(`/fulfillments/${encodeURIComponent(row.order_id)}`).catch(() => row)));
  box.innerHTML = details.map(row => `
    <article class="fulfillment">
      <header><strong>${escapeHtml(row.order_id)}</strong>${badge(row.status)}</header>
      <div>买家：${escapeHtml(row.buyer_id || '')}　份数：${row.quantity || 1}</div>
      ${(row.items || []).map(item => `
        <div class="item-row">
          <span>#${item.inventory_id} ${escapeHtml(item.email || '')}</span>
          <span>${badge(item.status)}</span>
        </div>`).join('')}
      ${row.last_error ? `<pre class="error-text">${escapeHtml(row.last_error)}</pre>` : ''}
      <details><summary>发货语句</summary><pre>${escapeHtml(row.delivery_text || '')}</pre></details>
    </article>
  `).join('');
}

async function loadSettings() {
  const data = await api('/settings');
  $('xianyuBaseUrl').value = data.xianyu_base_url || '';
  $('xianyuEndpoint').value = data.xianyu_send_endpoint || '/internal/accounts/{account_id}/send-message';
  $('xianyuAccountId').value = data.xianyu_account_id || '';
  $('xianyuToken').value = data.xianyu_api_token || '';
  $('cockpitBaseUrl').value = data.cockpit_base_url || '';
  $('cockpitToken').value = data.cockpit_api_token || '';
  $('codexCommand').value = data.codex_command || 'codex';
  $('codexPrompt').value = data.codex_prompt || '只回复：你好';
  $('deliveryTemplate').value = data.delivery_template || '';
}

async function loadAudit() {
  const list = await api('/audit?limit=80');
  $('auditList').innerHTML = list.map(row => `<div class="audit-item">
    <strong>${escapeHtml(row.event_type)}</strong> <span>${escapeHtml(row.created_at)}</span>
    <div>订单：${escapeHtml(row.order_id || '')}　库存：${row.inventory_id || ''}</div>
    <pre>${escapeHtml(row.payload || '{}')}</pre>
  </div>`).join('') || '<div class="audit-item">暂无审计日志</div>';
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadInventory(), loadFulfillments(), loadAudit()]);
}

function selectedJsonFiles() {
  const files = [...($('importFiles').files || []), ...($('importDir').files || [])];
  const seen = new Set();
  return files.filter(file => {
    const key = `${file.name}:${file.size}:${file.lastModified}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return file.name.toLowerCase().endsWith('.json');
  });
}

function bindActions() {
  $('refreshBtn').addEventListener('click', refreshAll);
  $('statusFilter').addEventListener('change', loadInventory);
  $('searchInput').addEventListener('input', () => setTimeout(loadInventory, 120));
  $('auditRefreshBtn').addEventListener('click', loadAudit);
  $('importFiles').addEventListener('change', () => $('fileImportHint').textContent = `已选择 ${selectedJsonFiles().length} 个 JSON 文件`);
  $('importDir').addEventListener('change', () => $('fileImportHint').textContent = `已选择 ${selectedJsonFiles().length} 个 JSON 文件`);

  $('importBtn').addEventListener('click', async () => {
    try {
      const payload = JSON.parse($('importText').value);
      const result = await api('/inventory/import-cpa', {
        method: 'POST',
        body: JSON.stringify({ payload, sync_cockpit: $('syncCockpit').checked }),
      });
      toast(`导入完成：新增 ${result.created}，跳过 ${result.skipped}`);
      await refreshAll();
    } catch (err) {
      toast(`导入失败：${err.message}`);
    }
  });

  $('importFilesBtn').addEventListener('click', async () => {
    const files = selectedJsonFiles();
    if (!files.length) return toast('请先选择 JSON 文件或目录');
    const form = new FormData();
    files.forEach(file => form.append('files', file, file.webkitRelativePath || file.name));
    form.append('sync_cockpit', $('syncCockpit').checked ? 'true' : 'false');
    try {
      const result = await api('/inventory/import-cpa-files', { method: 'POST', body: form });
      const failed = result.failed_files?.length || 0;
      toast(`文件导入完成：解析 ${result.parsed_files}/${result.files}，新增 ${result.created}，跳过 ${result.skipped}，失败 ${failed}`);
      await refreshAll();
    } catch (err) {
      toast(`文件导入失败：${err.message}`);
    }
  });

  $('shipBtn').addEventListener('click', async () => {
    try {
      const body = {
        order_id: $('orderId').value.trim(),
        buyer_id: $('buyerId').value.trim(),
        item_id: $('itemId').value.trim(),
        platform: $('platform').value.trim() || 'chatgpt',
        quantity: Number($('quantity').value || 1),
        send_to_xianyu: $('sendToXianyu').checked,
      };
      if (!body.order_id) throw new Error('请填写订单号');
      const result = await api('/fulfillments/ship', {
        method: 'POST',
        headers: { 'Idempotency-Key': `ui-ship-${body.order_id}` },
        body: JSON.stringify(body),
      });
      toast(`已出库：${result.items?.length || body.quantity} 份`);
      await refreshAll();
    } catch (err) {
      toast(`出库失败：${err.message}`);
    }
  });

  $('saveSettingsBtn').addEventListener('click', async () => {
    const values = {
      xianyu_base_url: $('xianyuBaseUrl').value.trim(),
      xianyu_send_endpoint: $('xianyuEndpoint').value.trim(),
      xianyu_account_id: $('xianyuAccountId').value.trim(),
      xianyu_api_token: $('xianyuToken').value.trim(),
      cockpit_base_url: $('cockpitBaseUrl').value.trim(),
      cockpit_api_token: $('cockpitToken').value.trim(),
      codex_command: $('codexCommand').value.trim(),
      codex_prompt: $('codexPrompt').value.trim(),
      delivery_template: $('deliveryTemplate').value,
    };
    await api('/settings', { method: 'PUT', body: JSON.stringify({ values }) });
    toast('设置已保存');
    await loadSettings();
  });

  $('previewBtn').addEventListener('click', async () => {
    await api('/settings', { method: 'PUT', body: JSON.stringify({ values: { delivery_template: $('deliveryTemplate').value } }) });
    const data = await api('/delivery/preview', { method: 'POST', body: JSON.stringify({ inventory_ids: [] }) });
    $('templatePreview').textContent = data.text;
  });
}

(async function init() {
  bindTabs();
  bindActions();
  await loadSettings();
  await refreshAll();
})();