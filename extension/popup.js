// 图文教程采集器 - 弹窗控制

const $ = function (id) { return document.getElementById(id); };

function send(msg) {
  return new Promise(function (resolve) {
    chrome.runtime.sendMessage(msg, function (res) {
      void chrome.runtime.lastError;
      resolve(res || {});
    });
  });
}

function refresh() {
  send({ type: 'status' }).then(function (s) {
    const rec = s.rec || {};
    const n = s.stored || 0;
    $('count').textContent = n;
    $('dot').className = 'dot' + (rec.on ? ' on' : '');
    $('title').textContent = rec.on ? '采集中…' : '图文教程采集器';
    $('btnStart').disabled = !!rec.on;
    $('btnStop').disabled = !rec.on;
    $('btnPause').disabled = !rec.on;
    $('btnPause').textContent = rec.paused ? '继续采集' : '暂停采集';
    $('host').innerHTML = rec.host
      ? ('只录：<b>' + rec.host + '</b>'
         + (rec.offDomain ? ('　已忽略 ' + rec.offDomain + ' 条站外动作') : ''))
      : '';
    $('btnExport').disabled = n === 0;
    $('btnClear').disabled = n === 0 && !rec.on;
    $('skipped').textContent = rec.skipped ? ('跳过 ' + rec.skipped + ' 张') : '';
    $('scrolls').textContent = rec.scrolls ? ('含滚动补采 ' + rec.scrolls + ' 张') : '';
  });
}

$('btnStart').onclick = function () {
  $('done').style.display = 'none';
  send({ type: 'start' }).then(refresh);
};

$('btnStop').onclick = function () {
  send({ type: 'stop' }).then(refresh);
};

$('btnPause').onclick = function () {
  chrome.runtime.sendMessage({ type: 'status' }, function (s) {
    void chrome.runtime.lastError;
    const isPaused = s && s.rec && s.rec.paused;
    send({ type: isPaused ? 'resume' : 'pause' }).then(refresh);
  });
};

$('btnExport').onclick = function () {
  chrome.storage.local.get(null, function (all) {
    const keys = Object.keys(all).filter(function (k) { return k.indexOf('step_') === 0; });
    const steps = keys.map(function (k) { return all[k]; })
                       .sort(function (a, b) { return a.index - b.index; });
    if (!steps.length) return;

    const withShot = steps.filter(function (s) { return !!s.shot; });
    const doc = {
      generator: 'tutorial-maker-extension/1.1.0',
      exported_at: new Date().toISOString(),
      pages: Array.from(new Set(steps.map(function (s) { return s.page; }))),
      viewport: steps[0].viewport || null,
      actions: withShot.map(function (s) {
        return {
          index: s.index,
          kind: s.kind,
          tag: s.tag,
          text: s.text,
          sensitive: s.sensitive,
          box: s.box,
          redact: s.redact,
          scrollY: s.scrollY,
          docH: s.docH,
          page_url: s.page,
          shot: s.shot
        };
      }),
      dropped: steps.length - withShot.length
    };

    const blob = new Blob([JSON.stringify(doc)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    a.href = url;
    a.download = 'tutorial-capture-' + stamp + '.json';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 8000);
    $('done').style.display = 'block';
  });
};

$('btnClear').onclick = function () {
  chrome.storage.local.get(null, function (all) {
    const keys = Object.keys(all).filter(function (k) { return k.indexOf('step_') === 0; });
    chrome.storage.local.remove(keys.concat(['rec']), function () {
      chrome.action.setBadgeText({ text: '' });
      refresh();
    });
  });
};

refresh();
