# -*- coding: utf-8 -*-
"""
网页端操作采集器（本地版 Scribe）
你在浏览器里正常操作，脚本自动：
  1. 每次点击/输入后截一张原图（无损 PNG，无视频压缩）
  2. 记录被点元素的精确边界 -> 直接作为高亮框坐标
  3. 识别输入框内容类型（手机号/邮箱/密码/证件号）-> 自动标记为待打码
  4. 输出 steps.json 骨架，可直接喂给 render.py 成稿

用法:
  python web_capture.py https://example.com/register
  # 浏览器打开后正常操作，操作完关闭浏览器窗口（或回终端按 Ctrl+C）
"""
import json, re, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright, Error as PWError

# 注入到每个页面的监听器：只记录，不改页面
RECORDER = r"""
window.__steps = window.__steps || [];
window.__seq = window.__seq || 0;

window.__sensitiveKind = function (el) {
  const v = (el.value || '').trim();
  const digits = v.replace(/[\s-]/g, '');
  if (el.type === 'password') return 'password';
  if (el.maxLength === 1) return 'otp';                       // 验证码单格
  if (el.inputMode === 'numeric' && el.maxLength > 1 && el.maxLength <= 8) return 'otp';
  if (/^1[3-9]\d{9}$/.test(digits)) return 'phone';
  if (/^[\w.+-]+@[\w-]+\.[\w.]{2,}$/.test(v)) return 'email';
  if (/^\d{17}[\dXx]$/.test(digits)) return 'idcard';
  if (/^\d{16,19}$/.test(digits)) return 'bankcard';
  return null;
};

window.__pick = function (e) {
  const t = e.target;
  if (!t || !t.tagName) return null;
  return t.closest('button,a,input,textarea,select,label,[role=button],[contenteditable=true]') || t;
};

// 截图前调用：扫描全页敏感输入框，返回需打码的区域（不依赖"哪个元素触发了事件"）
window.__scanSensitive = function () {
  const out = [];
  document.querySelectorAll('input,textarea').forEach(function (el) {
    const k = window.__sensitiveKind(el);
    if (!k || !el.value) return;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) return;
    // 被弹窗/遮罩盖住的元素本身不可见，不必打码——否则会在弹窗上糊出白斑
    const top = document.elementFromPoint(
      Math.min(innerWidth - 1, Math.max(0, r.x + r.width / 2)),
      Math.min(innerHeight - 1, Math.max(0, r.y + r.height / 2)));
    if (!top) return;
    if (!(top === el || el.contains(top) || top.contains(el))) return;
    out.push({kind: k,
              box: {x: Math.max(0, r.x) / innerWidth, y: Math.max(0, r.y) / innerHeight,
                    w: r.width / innerWidth, h: r.height / innerHeight}});
  });
  return out;
};

window.__record = function (kind, el) {
  if (!el || !el.getBoundingClientRect) return;
  const r = el.getBoundingClientRect();
  if (r.width < 2 || r.height < 2) return;
  const kindOfField = window.__sensitiveKind(el);
  // 密码/验证码的明文绝不落盘
  const raw = (el.innerText || el.value || el.getAttribute('placeholder') ||
               el.getAttribute('aria-label') || '').trim().slice(0, 60);
  const safeText = kindOfField ? '••••' : raw;   // 任何敏感字段都不落明文
  window.__seq += 1;
  window.__steps.push({
    seq: window.__seq,
    ts: Date.now(),
    kind: kind,
    tag: (el.tagName || '').toLowerCase(),
    text: safeText,
    sensitive: kindOfField,
    box: {
      x: Math.max(0, r.x) / innerWidth,
      y: Math.max(0, r.y) / innerHeight,
      w: r.width / innerWidth,
      h: r.height / innerHeight
    },
    page: location.href
  });
};

document.addEventListener('click', e => window.__record('click', window.__pick(e)), true);
document.addEventListener('submit', e => window.__record('submit', window.__pick(e)), true);

// 输入：用防抖，既不漏"填完一个字段"，也不为每个字符记一条
window.__inputTimers = window.__inputTimers || new WeakMap();
document.addEventListener('input', function (e) {
  const el = window.__pick(e);
  if (!el) return;
  const prev = window.__inputTimers.get(el);
  if (prev) clearTimeout(prev);
  window.__inputTimers.set(el, setTimeout(function () {
    window.__record('input', el);
  }, 500));
}, true);
"""


def slug(url):
    s = re.sub(r"^https?://", "", url).split("?")[0].strip("/")
    s = re.sub(r"[^\w.-]+", "_", s)
    return (s[:48] or "page")


def capture(url, outdir, timeout_min=30, settle=0.45, _driver=None):
    """_driver: 仅自检用，传一个 generator，在采集循环里逐步驱动页面。"""
    out = Path(outdir)
    (out / "shots").mkdir(parents=True, exist_ok=True)
    for f in (out / "shots").glob("*.png"):
        f.unlink()

    actions, seen = [], set()
    n = 0

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome", headless=False)
        except PWError:
            browser = p.chromium.launch(headless=False)   # 回退到自带内核

        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  device_scale_factor=1)
        ctx.add_init_script(RECORDER)
        page = ctx.new_page()
        page.on("dialog", lambda d: d.accept())
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        print("\n浏览器已打开。请正常完成操作（点击、填写、提交都可以）。")
        print("操作完成后：直接关闭浏览器窗口即可结束采集。\n")

        closed = False
        browser.on("disconnected", lambda _: None)
        deadline = time.time() + timeout_min * 60
        driver = _driver(page) if _driver else None
        driver_done = driver is None
        idle = 0

        while time.time() < deadline:
            if driver and not driver_done:
                try:
                    next(driver)
                except StopIteration:
                    driver_done = True
                except Exception as e:
                    driver_done = True
                    print(f"  [自检驱动结束] {e}")
            try:
                if not ctx.pages:
                    closed = True
                    break
                cur = ctx.pages[-1]
                steps = cur.evaluate("window.__steps || []")
            except PWError:
                if not browser.is_connected():
                    closed = True
                    break
                time.sleep(0.3)
                continue

            fresh = [s for s in steps if s["ts"] not in seen]
            if fresh:
                for s in fresh:
                    seen.add(s["ts"])
                last = fresh[-1]
                time.sleep(settle)                      # 等页面响应完再截
                n += 1
                shot = out / "shots" / f"step{n:02d}.png"
                ok = False
                try:
                    scanned = cur.evaluate(
                        "window.__scanSensitive ? window.__scanSensitive() : []")
                except PWError:
                    scanned = []
                for _ in range(3):
                    try:
                        cur.screenshot(path=str(shot), animations="disabled")
                        ok = True
                        break
                    except PWError:
                        time.sleep(0.35)
                if not ok:
                    n -= 1
                    continue
                # 打码区来自全页扫描，而不是"哪个元素触发了事件"
                redact = [[b["box"]["x"], b["box"]["y"], b["box"]["w"], b["box"]["h"]]
                          for b in scanned]
                hb = last["box"]
                actions.append({
                    "index": n, "seq": last["seq"], "kind": last["kind"],
                    "tag": last["tag"], "text": last["text"],
                    "sensitive": last["sensitive"],
                    "box": hb, "page_url": last["page"],
                    "file": str(shot), "title": "", "body": "",
                    "redact": redact,
                    "highlight": [[hb["x"], hb["y"], hb["w"], hb["h"]]],
                    "notes": []
                })
                extra = f" +{len(redact)} 处打码" if redact else ""
                print(f"  已截取第 {n} 步：{last['kind']} <{last['tag']}> "
                      f"{last['text'][:30]}{extra}")
            time.sleep(0.12)
            if driver and driver_done:
                idle += 1
                if idle > 25:                 # 自检驱动结束后约 3 秒无新动作则收工
                    break
            else:
                idle = 0
            if not browser.is_connected():
                closed = True
                break

        try:
            browser.close()
        except Exception:
            pass

    if not actions:
        print("没有采集到任何操作，请确认在打开后的浏览器窗口里完成了点击/填写。")
        return None

    doc = {
        "doc": {"title": f"{slug(url)} 操作流程",
                "intro": "按下面步骤操作即可完成。",
                "meta": "适用：网页端",
                "outro": "截图中的账号信息已做脱敏处理。"},
        "steps": actions
    }
    (out / "steps.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    auto_mask = sum(1 for a in actions if a["redact"])
    print(f"\n采集完成：{len(actions)} 步 -> {out/'steps.json'}")
    print(f"  其中 {auto_mask} 步已自动标记打码区（手机号/密码/邮箱/证件号）")
    print(f"  截图目录：{out/'shots'}")
    print("\n下一步：检查 steps.json 补写标题文案，再运行 render.py 成稿。")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: python web_capture.py <网址> [输出目录]")
    capture(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "capture")
