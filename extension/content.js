// 图文教程采集器 - 页面监听脚本
// 做四件事：判断哪些是步骤、算坐标、识别敏感字段、滚动分段补采（长页面不漏内容）。

(function () {
  if (window.__tcInjected) return;
  window.__tcInjected = true;

  let recording = false;
  let paused = false;
  let seq = 0;
  const inputTimers = new WeakMap();

  chrome.storage.local.get('rec', function (r) {
    recording = !!(r && r.rec && r.rec.on);
    paused = !!(r && r.rec && r.rec.paused);
  });

  chrome.storage.onChanged.addListener(function (changes, area) {
    if (area === 'local' && changes.rec) {
      const v = changes.rec.newValue || {};
      recording = !!v.on;
      paused = !!v.paused;
      if (recording && !paused) { seq = 0; lastScrollY = null; }
    }
  });

  // ---- 敏感字段识别 ----
  function sensitiveKind(el) {
    const v = (el.value || '').trim();
    const digits = v.replace(/[\s-]/g, '');
    if (el.type === 'password') return 'password';
    if (el.maxLength === 1) return 'otp';
    if (el.inputMode === 'numeric' && el.maxLength > 1 && el.maxLength <= 8) return 'otp';
    if (/^1[3-9]\d{9}$/.test(digits)) return 'phone';
    if (/^[\w.+-]+@[\w-]+\.[\w.]{2,}$/.test(v)) return 'email';
    if (/^\d{17}[\dXx]$/.test(digits)) return 'idcard';
    if (/^\d{16,19}$/.test(digits)) return 'bankcard';
    return null;
  }

  function pickTarget(e) {
    const t = e.target;
    if (!t || !t.tagName) return null;
    return t.closest(
      'button,a,input,textarea,select,label,[role=button],[contenteditable=true]'
    ) || t;
  }

  // 截图前由 background 请求：当前页所有"可见且有值"的敏感输入框
  function scanSensitive() {
    const out = [];
    document.querySelectorAll('input,textarea').forEach(function (el) {
      const k = sensitiveKind(el);
      if (!k || !el.value) return;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) return;
      const top = document.elementFromPoint(
        Math.min(innerWidth - 1, Math.max(0, r.x + r.width / 2)),
        Math.min(innerHeight - 1, Math.max(0, r.y + r.height / 2))
      );
      if (!top) return;
      if (!(top === el || el.contains(top) || top.contains(el))) return;  // 被弹窗盖住，不可见
      out.push({
        kind: k,
        box: {
          x: Math.max(0, r.x) / innerWidth,
          y: Math.max(0, r.y) / innerHeight,
          w: r.width / innerWidth,
          h: r.height / innerHeight
        }
      });
    });
    return out;
  }

  const KIND_LABEL = {
    password: '••••', otp: '••••', phone: '手机号',
    email: '邮箱', idcard: '身份证号', bankcard: '银行卡号'
  };

  function safeText(el, kind) {
    // 任何被判定为敏感的字段，明文一律不落盘——含手机号、身份证、银行卡、邮箱。
    if (kind) return KIND_LABEL[kind] || '••••';
    const t = (el.innerText || el.value || el.getAttribute('placeholder') ||
               el.getAttribute('aria-label') || el.getAttribute('title') || '')
              .trim().replace(/\s+/g, ' ').slice(0, 60);
    return t;
  }

  function docHeight() {
    const d = document.documentElement, b = document.body;
    return Math.round(Math.max(d.scrollHeight, b ? b.scrollHeight : 0, innerHeight));
  }

  // 所有记录都带上 scrollY / docH：
  // 事后要把同页多张图拼成整页长图，靠的就是这两个数，图像匹配是算不准的。
  function makePayload(kind, el, k) {
    const payload = {
      seq: ++seq,
      ts: Date.now(),
      kind: kind,
      tag: el ? (el.tagName || '').toLowerCase() : '',
      text: el ? safeText(el, k) : '',
      sensitive: k || null,
      box: null,
      redact: scanSensitive().map(function (s) { return [
        s.box.x, s.box.y, s.box.w, s.box.h]; }),
      viewport: { w: innerWidth, h: innerHeight },
      scrollY: Math.round(window.scrollY),
      docH: docHeight(),
      page: location.href
    };
    if (el) {
      const r = el.getBoundingClientRect();
      payload.box = { x: Math.max(0, r.x) / innerWidth, y: Math.max(0, r.y) / innerHeight,
                      w: r.width / innerWidth, h: r.height / innerHeight };
    }
    return payload;
  }

  function send(payload, delay) {
    setTimeout(function () {
      if (!recording) return;
      try {
        chrome.runtime.sendMessage({ type: 'step', payload: payload });
      } catch (e) {
        // 扩展重载后旧 content script 会失联，忽略
      }
    }, delay || 0);
  }

  function record(kind, el, delay) {
    if (!recording || paused || !el) return;
    // 坐标必须在事件瞬间取：页面一切换，被点元素会被 display:none，rect 归零
    const r0 = el.getBoundingClientRect();
    if (r0.width < 2 || r0.height < 2) return;
    send(makePayload(kind, el, sensitiveKind(el)), delay);
  }

  document.addEventListener('click', function (e) {
    record('click', pickTarget(e), 0);
  }, true);

  document.addEventListener('submit', function (e) {
    record('submit', pickTarget(e), 0);
  }, true);

  // ---- 滚动分段补采 ----
  // 点击只发生在有交互的地方，纯阅读的段落（长表单的中段、条款正文、结果页下半）
  // 永远不会被记录，导出后必然缺图。滚停后补一帧，条件：本次滚动幅度 ≥ 半屏。
  let scrollIdle = null;
  let lastScrollY = null;
  const SCROLL_MIN_RATIO = 0.5;

  function takeScrollShot() {
    if (!recording || paused) return;
    const y = Math.round(window.scrollY);
    if (lastScrollY !== null && Math.abs(y - lastScrollY) < innerHeight * SCROLL_MIN_RATIO) return;
    lastScrollY = y;
    send(makePayload('scroll', null, null), 0);
  }

  window.addEventListener('scroll', function () {
    if (!recording || paused) return;
    clearTimeout(scrollIdle);
    scrollIdle = setTimeout(takeScrollShot, 420);
  }, { passive: true });

  // 首屏也补一张：有些页面打开就有一屏内容，没有任何点击
  window.addEventListener('load', function () {
    setTimeout(function () {
      if (recording && !paused && lastScrollY === null) takeScrollShot();
    }, 900);
  });

  // 悬停预截图：点击会把选项变灰/跳转，所以趁鼠标停留时先拍下"未点击"的原貌。
  // 点击时若预截图仍新鲜且元素一致，就用它，观感更自然。
  let hoverTimer = null;
  let hoverEl = null;

  document.addEventListener('mouseover', function (e) {
    if (!recording || paused) return;
    const el = pickTarget(e);
    if (!el || el === hoverEl) return;
    hoverEl = el;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(function () {
      if (!recording || paused) return;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;
      const k = sensitiveKind(el);
      try {
        chrome.runtime.sendMessage({
          type: 'preshot',
          payload: {
            tag: (el.tagName || '').toLowerCase(),
            text: safeText(el, k),
            box: { x: Math.max(0, r.x) / innerWidth, y: Math.max(0, r.y) / innerHeight,
                   w: r.width / innerWidth, h: r.height / innerHeight }
          }
        });
      } catch (err) { /* 扩展重载后失联，忽略 */ }
    }, 320);
  }, true);

  // 输入：500ms 防抖，既不漏"填完一个字段"，也不为每个字符记一条
  document.addEventListener('input', function (e) {
    if (!recording) return;
    const el = pickTarget(e);
    if (!el) return;
    const prev = inputTimers.get(el);
    if (prev) clearTimeout(prev);
    inputTimers.set(el, setTimeout(function () {
      record('input', el, 0);
    }, 500));
  }, true);
})();
