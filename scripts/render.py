# -*- coding: utf-8 -*-
"""
步骤数据 -> 成品图文教程
输入: steps.json  (title/body/redact/highlight，坐标均为 0~1 归一化)
输出: images/stepNN.png + tutorial.md + tutorial.html(单文件,可粘公众号)
"""
import base64, json, sys, html
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ACCENT = (217, 45, 45)      # 高亮红
BRAND = "#1D4ED8"


def font_path(bold=False):
    cands = ["C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
             "C:/Windows/Fonts/simhei.ttf" if bold else "C:/Windows/Fonts/simsun.ttc",
             "/System/Library/Fonts/PingFang.ttc",
             "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold
             else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"]
    for c in cands:
        if Path(c).exists():
            return c
    return None


def jfont(size, bold=False):
    p = font_path(bold)
    return ImageFont.truetype(p, size) if p else ImageFont.load_default()


# ---------- 图像处理 ----------
def px(box, w, h, pad_px=0):
    """归一化 [x,y,w,h] -> 像素 [x0,y0,x1,y1]，向外扩 pad_px 并夹紧到画面内。
    打码必须留安全边距：漏一个字符等于没打码。"""
    x, y, bw, bh = box
    x0, y0 = int(x * w) - pad_px, int(y * h) - pad_px
    x1, y1 = int((x + bw) * w) + pad_px, int((y + bh) * h) + pad_px
    return max(0, x0), max(0, y0), min(w, x1), min(h, y1)


def mosaic(im, box, block=10):
    """像素化打码：安全、且读者一眼看出是刻意脱敏"""
    x0, y0, x1, y1 = box
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    region = im.crop((x0, y0, x1, y1))
    small = region.resize((max(1, (x1 - x0) // block), max(1, (y1 - y0) // block)), Image.BILINEAR)
    im.paste(small.resize((x1 - x0, y1 - y0), Image.NEAREST), (x0, y0))


def blur(im, box, r=16):
    x0, y0, x1, y1 = box
    region = im.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(r))
    im.paste(region, (x0, y0))


def solid(im, box, color=(176, 190, 207)):
    ImageDraw.Draw(im).rectangle(box, fill=color)


def annotate(im, box, color=ACCENT, radius=None, width=None, label=None):
    """高亮框。默认不画序号（序号由标题承担），需要时置于框外上方，绝不遮挡内容。
    圆角按元素自身尺寸自适应，避免小按钮上框显得比元素大。"""
    w, h = im.size
    # 描边压到 2px、填充压到 12%：高亮框只做事后标注，不该比被框元素更抢眼
    width = width or max(2, round(w / 550))
    d = ImageDraw.Draw(im, "RGBA")
    x0, y0, x1, y1 = box
    if radius is None:
        radius = max(4, min(10, round(min(x1 - x0, y1 - y0) * 0.18)))
    d.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=color + (18,), outline=color + (230,), width=width)
    if label:
        fs = max(14, round(w / 52))
        f = jfont(fs, True)
        tw = d.textlength(str(label), font=f)
        pad = round(fs * 0.42)
        bw, bh = tw + pad * 2, fs + pad * 2
        bx0, by0 = x0, y0 - bh - 4
        if by0 < 2:                      # 顶部放不下就落到框内顶部，仍不越出画面
            by0 = y0 + 4
        d.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=round(fs * 0.45), fill=color + (255,))
        d.text((bx0 + pad, by0 + pad - 1), str(label), font=f, fill=(255, 255, 255, 255))


def arrow(im, start, end, color=ACCENT):
    from math import atan2, cos, sin, pi
    w, h = im.size
    d = ImageDraw.Draw(im, "RGBA")
    x0, y0 = start[0] * w, start[1] * h
    x1, y1 = end[0] * w, end[1] * h
    lw = max(3, round(w / 340))
    d.line([x0, y0, x1, y1], fill=color + (255,), width=lw)
    ang = atan2(y1 - y0, x1 - x0)
    L = max(14, round(w / 60))
    for s in (0.45, -0.45):
        d.line([x1, y1, x1 - L * cos(ang - s), y1 - L * sin(ang - s)], fill=color + (255,), width=lw)


def process(step, out_path, max_width=1100, style="mosaic"):
    im = Image.open(step["file"]).convert("RGB")
    if im.width > max_width:
        im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
    w, h = im.size

    # 打码边距：横向留余量防漏字，纵向几乎不外扩——否则会糊住上方的字段标签，
    # 读者就看不出这些框是干什么的。隐私与可读性必须同时成立。
    pad_x = max(4, round(w * 0.004))
    pad_y = max(1, round(h * 0.002))
    for box in step.get("redact", []):
        x0, y0, x1, y1 = px(box, w, h)
        b = (max(0, x0 - pad_x), max(0, y0 - pad_y), min(w, x1 + pad_x), min(h, y1 + pad_y))
        {"blur": lambda: blur(im, b), "solid": lambda: solid(im, b)}.get(style, lambda: mosaic(im, b))()

    for box in step.get("highlight", []):
        annotate(im, px(box, w, h), label=step.get("badge"))

    for a in step.get("arrows", []):
        arrow(im, (a[0], a[1]), (a[2], a[3]))

    im.save(out_path, quality=92)
    return out_path


# ---------- 输出版式 ----------
def build_md(doc, steps, rel_img):
    L = [f"# {doc['title']}", ""]
    if doc.get("intro"):
        L += [doc["intro"], ""]
    if doc.get("meta"):
        L += [f"> {doc['meta']}", ""]
    for s in steps:
        L += [f"## 第 {s['index']} 步 · {s['title']}", ""]
        if s.get("body"):
            L += [s["body"], ""]
        L += [f"![第 {s['index']} 步]({rel_img}/{Path(s['out']).name})", ""]
        for n in s.get("notes", []):
            L += [f"- {n}"]
        if s.get("notes"):
            L += [""]
    if doc.get("outro"):
        L += ["---", "", doc["outro"], ""]
    return "\n".join(L)


def para(text):
    """正文里的空行视为分段：Markdown 认 \n\n，HTML 不认，得手动拆成段落。"""
    return '</p><p class="body">'.join(
        html.escape(x).replace("\n", "<br>") for x in text.split("\n\n"))


def build_html(doc, steps):
    def b64(p):
        return "data:image/png;base64," + base64.b64encode(Path(p).read_bytes()).decode()

    cards = []
    for s in steps:
        notes = "".join(f"<li>{html.escape(n)}</li>" for n in s.get("notes", []))
        cards.append(f"""
    <section class="step">
      <div class="head"><span class="num">{s['index']}</span><h2>{html.escape(s['title'])}</h2></div>
      {f'<p class="body">{para(s["body"])}</p>' if s.get('body') else ''}
      <figure><img src="{b64(s['out'])}" alt="第{s['index']}步"></figure>
      {f'<ul class="notes">{notes}</ul>' if notes else ''}
    </section>""")

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(doc['title'])}</title>
<style>
  :root{{--brand:{BRAND};--ink:#0F172A;--sub:#64748B;--line:#E2E8F0;--bg:#F8FAFC}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--bg);font-family:-apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
       color:var(--ink);line-height:1.75;-webkit-font-smoothing:antialiased}}
  .wrap{{max-width:720px;margin:0 auto;padding:36px 20px 64px}}
  header{{border-bottom:3px solid var(--brand);padding-bottom:18px;margin-bottom:32px}}
  h1{{font-size:26px;margin:0 0 10px;letter-spacing:-.3px}}
  .intro{{color:var(--sub);font-size:15px;margin:0}}
  .meta{{display:inline-block;margin-top:14px;padding:4px 10px;background:#EEF2FF;color:var(--brand);
        border-radius:6px;font-size:13px;font-weight:600}}
  .step{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:22px;
        margin-bottom:22px;box-shadow:0 1px 2px rgba(15,23,42,.04)}}
  .head{{display:flex;align-items:center;gap:12px;margin-bottom:12px}}
  .num{{flex:0 0 30px;height:30px;border-radius:9px;background:var(--brand);color:#fff;
       font-weight:700;font-size:15px;display:flex;align-items:center;justify-content:center}}
  h2{{font-size:18px;margin:0;letter-spacing:-.2px}}
  .body{{margin:0 0 14px;font-size:15px;color:#334155}}
  figure{{margin:0;border:1px solid var(--line);border-radius:10px;overflow:hidden;background:#fff}}
  figure img{{display:block;width:100%;height:auto}}
  .notes{{margin:14px 0 0;padding-left:20px;font-size:14px;color:var(--sub)}}
  .notes li{{margin:4px 0}}
  footer{{margin-top:34px;padding-top:18px;border-top:1px solid var(--line);
         font-size:14px;color:var(--sub)}}
</style></head><body><div class="wrap">
  <header>
    <h1>{html.escape(doc['title'])}</h1>
    {f'<p class="intro">{html.escape(doc["intro"])}</p>' if doc.get('intro') else ''}
    {f'<span class="meta">{html.escape(doc["meta"])}</span>' if doc.get('meta') else ''}
  </header>
  {''.join(cards)}
  {f'<footer>{html.escape(doc["outro"])}</footer>' if doc.get('outro') else ''}
</div></body></html>"""


# ---------- 主流程 ----------
def resolve_shot(p, base):
    """图片路径优先按 steps.json 所在目录解析，找不到再回退当前目录。
    这样一个 steps.json 可以连同它的 shots/ 一起搬走，不必依赖 cwd。"""
    q = Path(p)
    if q.is_absolute():
        return q
    cand = base / q
    if cand.exists():
        return cand
    return q if q.exists() else cand


def render(steps_json, outdir, style="mosaic"):
    data = json.loads(Path(steps_json).read_text(encoding="utf-8"))
    base = Path(steps_json).resolve().parent
    doc = data.get("doc", {"title": "操作教程"})
    steps = [s for s in data["steps"] if s.get("file")]
    for s in steps:
        s["file"] = str(resolve_shot(s["file"], base))
    outdir = Path(outdir)
    imgdir = outdir / "images"
    imgdir.mkdir(parents=True, exist_ok=True)

    for s in steps:
        s["out"] = str(imgdir / f"step{s['index']:02d}.png")
        process(s, s["out"], style=style)

    md = build_md(doc, steps, "images")
    (outdir / "tutorial.md").write_text(md, encoding="utf-8")
    (outdir / "tutorial.html").write_text(build_html(doc, steps), encoding="utf-8")
    (outdir / "steps.rendered.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"完成: {len(steps)} 步 -> {outdir}")
    print(f"  {outdir/'tutorial.md'}\n  {outdir/'tutorial.html'}")
    return outdir


if __name__ == "__main__":
    sj = sys.argv[1] if len(sys.argv) > 1 else "work/steps.json"
    od = sys.argv[2] if len(sys.argv) > 2 else "output"
    render(sj, od, style=sys.argv[3] if len(sys.argv) > 3 else "mosaic")
