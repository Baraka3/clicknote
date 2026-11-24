// 图文教程采集器 - 后台服务
// 职责：域名限定（只录开始时的站点）、暂停/继续、限速截图、悬停预截图、落盘存储。

const MIN_GAP_MS = 520;        // captureVisibleTab 硬限制 2 次/秒，取 520ms 留余量
const PRESHOT_TTL_MS = 5000;   // 预截图的保鲜期

let lastCaptureAt = 0;
const preshots = {};           // tabId -> { dataUrl, ts, tag, text }

function rootHost(h) {
  if (!h) return '';
  const parts = String(h).toLowerCase().replace(/^www\./, '').split('.');
  return parts.length >= 2 ? parts.slice(-2).join('.') : parts.join('.');
}

function hostOfUrl(u) {
  try { return rootHost(new URL(u).hostname); } catch (e) { return ''; }
}

function blankRec() {
  return { on: false, paused: false, start: 0, count: 0, skipped: 0, offDomain: 0, scrolls: 0, host: '' };
}

function ensureRec(cb) {
  chrome.storage.local.get('rec', function (r) {
    cb(Object.assign(blankRec(), r.rec || {}));
  });
}

function setBadge(rec) {
  if (!rec.on) { chrome.action.setBadgeText({ text: '' }); return; }
  const txt = rec.paused ? '⏸' : String(rec.count || 0);
  chrome.action.setBadgeText({ text: txt });
  chrome.action.setBadgeBackgroundColor({ color: rec.paused ? '#94A3B8' : '#1D4ED8' });
}

function saveItem(rec, p, dataUrl) {
  rec.count = (rec.count || 0) + 1;
  if (p.kind === 'scroll') rec.scrolls = (rec.scrolls || 0) + 1;
  const patch = { rec: rec };
  patch['step_' + rec.count] = {
    index: rec.count, seq: p.seq, ts: p.ts, kind: p.kind, tag: p.tag,
    text: p.text, sensitive: p.sensitive, box: p.box, redact: p.redact || [],
    viewport: p.viewport, scrollY: p.scrollY, docH: p.docH,
    page: p.page, shot: dataUrl || null,
    no_shot: !dataUrl
  };
  chrome.storage.local.set(patch, function () { setBadge(rec); });
}

chrome.runtime.onInstalled.addListener(function () {
  chrome.storage.local.get('rec', function (r) {
    if (!r.rec) chrome.storage.local.set({ rec: blankRec() });
  });
});

chrome.runtime.onMessage.addListener(function (msg, sender, sendResponse) {
  if (msg.type === 'start') {
    // 记住开录时所在的站点，之后只录这个站点，切走到别处自动忽略
    chrome.tabs.query({ active: true, lastFocusedWindow: true }, function (tabs) {
      const host = tabs && tabs[0] ? hostOfUrl(tabs[0].url) : '';
      const rec = Object.assign(blankRec(), { on: true, start: Date.now(), host: host });
      chrome.storage.local.set({ rec: rec }, function () {
        setBadge(rec);
        sendResponse({ ok: true, host: host });
      });
    });
    return true;
  }

  if (msg.type === 'stop' || msg.type === 'pause' || msg.type === 'resume') {
    ensureRec(function (rec) {
      if (msg.type === 'stop') rec.on = false;
      if (msg.type === 'pause') rec.paused = true;
      if (msg.type === 'resume') rec.paused = false;
      chrome.storage.local.set({ rec: rec }, function () {
        setBadge(rec);
        sendResponse({ ok: true });
      });
    });
    return true;
  }

  if (msg.type === 'status') {
    ensureRec(function (rec) {
      chrome.storage.local.get(null, function (all) {
        const n = Object.keys(all).filter(function (k) { return k.indexOf('step_') === 0; }).length;
        sendResponse({ rec: rec, stored: n });
      });
    });
    return true;
  }

  if (msg.type === 'preshot') return handlePreshot(msg, sender, sendResponse);
  if (msg.type === 'step') return handleStep(msg, sender, sendResponse);
  return false;
});

// 悬停时先拍一张"未点击"的原貌，供 click 复用
function handlePreshot(msg, sender, sendResponse) {
  const tab = sender.tab;
  if (!tab) { sendResponse({ ok: false }); return false; }
  ensureRec(function (rec) {
    if (!rec.on || rec.paused) { sendResponse({ ok: false }); return; }
    const now = Date.now();
    const prev = preshots[tab.id];
    if (prev && now - prev.ts < 600) { sendResponse({ ok: false }); return; }
    if (now - lastCaptureAt < MIN_GAP_MS) { sendResponse({ ok: false }); return; }

    chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' }, function (dataUrl) {
      if (chrome.runtime.lastError || !dataUrl) { sendResponse({ ok: false }); return; }
      lastCaptureAt = Date.now();
      preshots[tab.id] = {
        dataUrl: dataUrl, ts: Date.now(),
        tag: msg.payload && msg.payload.tag, text: msg.payload && msg.payload.text
      };
      sendResponse({ ok: true });
    });
  });
  return true;
}

function handleStep(msg, sender, sendResponse) {
  const tab = sender.tab;
  if (!tab) { sendResponse({ ok: false }); return false; }

  ensureRec(function (rec) {
    if (!rec.on) { sendResponse({ ok: false, reason: 'not-recording' }); return; }
    if (rec.paused) { sendResponse({ ok: false, reason: 'paused' }); return; }

    const p = msg.payload || {};
    const pageHost = hostOfUrl(p.page);
    // 域名限定：只收与开录时同一站点（含其子域名）的动作
    if (rec.host && pageHost && pageHost !== rec.host) {
      rec.offDomain = (rec.offDomain || 0) + 1;
      chrome.storage.local.set({ rec: rec });
      sendResponse({ ok: false, reason: 'off-domain' });
      return;
    }

    // 优先复用悬停预截图：那是点击前的原始状态，观感更自然
    const pre = preshots[tab.id];
    if (pre && Date.now() - pre.ts < PRESHOT_TTL_MS
        && pre.tag === p.tag && pre.text === p.text) {
      delete preshots[tab.id];
      saveItem(rec, p, pre.dataUrl);
      sendResponse({ ok: true, index: rec.count, reused: 'preshot' });
      return;
    }

    const now = Date.now();
    if (now - lastCaptureAt < MIN_GAP_MS) {
      // 截图有硬上限，但"这一步存在"不能丢：保留记录、标记无图
      rec.skipped = (rec.skipped || 0) + 1;
      saveItem(rec, p, null);
      sendResponse({ ok: false, reason: 'throttled' });
      return;
    }

    chrome.tabs.query({ active: true, windowId: tab.windowId }, function (tabs) {
      if (!tabs || !tabs[0] || tabs[0].id !== tab.id) {
        sendResponse({ ok: false, reason: 'not-active' });
        return;
      }
      chrome.tabs.captureVisibleTab(tab.windowId, { format: 'png' }, function (dataUrl) {
        if (chrome.runtime.lastError || !dataUrl) {
          rec.skipped = (rec.skipped || 0) + 1;
          saveItem(rec, p, null);
          sendResponse({ ok: false, reason: 'capture-failed' });
          return;
        }
        lastCaptureAt = Date.now();
        saveItem(rec, p, dataUrl);
        sendResponse({ ok: true, index: rec.count });
      });
    });
  });
  return true;
}
