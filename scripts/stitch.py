# -*- coding: utf-8 -*-
"""
把同一页面的多张视口截图按 scrollY 拼成整页长图。

前提：扩展 v1.1.0+ 导出的 JSON 里每帧带 scrollY / docH。
旧素材没有记录滚动位置，图像匹配算不准（表单插入错误提示会改变布局），
所以那种情况脚本会直接拒绝，不做瞎猜。

打码在拼接之后统一在画布上做，用的是所有帧 redact 的并集（换算到页面坐标）。
这样即使某一帧漏标了敏感框，拼出来的长图也不会露。

用法:
  python stitch.py <capture目录> [输出目录] [solid|mosaic|blur]

输入: <capture>/pages.json（import_capture.py 生成）
输出: <out>/page01.png ... 与 <out>/pages.md 索引
"""
import json, sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PAD_X_RATIO = 0.004
PAD_Y_RATIO = 0.002
MIN_OVERLAP = 24           # scrollY 几乎重合才合并，否则每帧都留着补内容


def merge_redacts(frames, vw, vh):
    """把各帧的视口坐标 redact 换算到页面坐标，去掉重复的框。"""
    out = []
    for f in frames:
        for b in (f.get("redact") or []):
            x, y, w, h = b
            box = (round(x * vw), round(f["scroll_y"] + y * vh),
                   round(w * vw), round(h * vh))
            dup = False
            for o in out:
                if abs(o[0] - box[0]) < 6 and abs(o[1] - box[1]) < 6 \
                   and abs(o[2] - box[2]) < 6 and abs(o[3] - box[3]) < 6:
                    dup = True
                    break
            if not dup:
                out.append(box)
    return out


def apply_redacts(canvas, boxes, style="solid"):
    w, h = canvas.size
    pad_x, pad_y = max(3, round(w * PAD_X_RATIO)), max(1, round(h * PAD_Y_RATIO))
    for (x, y, bw, bh) in boxes:
        x0, y0 = max(0, x - pad_x), max(0, y - pad_y)
        x1, y1 = min(w, x + bw + pad_x), min(h, y + bh + pad_y)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        if style == "mosaic":
            r = canvas.crop((x0, y0, x1, y1))
            r = r.resize((max(1, (x1 - x0) // 10), max(1, (y1 - y0) // 10)), Image.BILINEAR)
            canvas.paste(r.resize((x1 - x0, y1 - y0), Image.NEAREST), (x0, y0))
        elif style == "blur":
            canvas.paste(canvas.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(16)), (x0, y0))
        else:
            ImageDraw.Draw(canvas).rectangle((x0, y0, x1, y1), fill=(176, 190, 207))


def stitch(capture_dir, outdir, style="solid", max_height=12000):
    cap = Path(capture_dir)
    pages_file = cap / "pages.json"
    if not pages_file.exists():
        raise SystemExit(f"找不到 {pages_file}，先跑 import_capture.py")
    pages = json.loads(pages_file.read_text(encoding="utf-8"))

    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    index = []
    k = 0

    for url, frames in pages.items():
        usable = [f for f in frames if f.get("scroll_y") is not None]
        if len(usable) < 2:
            index.append({"page": url, "file": None, "frames": len(usable),
                          "note": "帧数不足或无 scrollY"})
            continue

        usable.sort(key=lambda f: (f["scroll_y"], f["file"]))
        kept = []
        for f in usable:
            if kept and f["scroll_y"] - kept[-1]["scroll_y"] < MIN_OVERLAP:
                kept[-1] = f          # 位置几乎重合，用更新的那张
            else:
                kept.append(f)

        first = Image.open(kept[0]["file"]).convert("RGB")
        vw, vh = first.size
        doc_h = max([f.get("doc_h") or 0 for f in kept] +
                    [f["scroll_y"] + vh for f in kept])
        canvas_h = min(doc_h, max_height)

        canvas = Image.new("RGB", (vw, canvas_h), "white")
        for f in kept:
            if f["scroll_y"] > canvas_h:
                continue
            im = Image.open(f["file"]).convert("RGB")
            if im.size != (vw, vh):
                im = im.resize((vw, vh), Image.LANCZOS)
            canvas.paste(im, (0, f["scroll_y"]))

        apply_redacts(canvas, merge_redacts(kept, vw, vh), style)

        k += 1
        dst = out / f"page{k:02d}.png"
        canvas.save(dst)
        covered = min(1.0, (max(f["scroll_y"] for f in kept) + vh) / canvas_h)
        index.append({"page": url, "file": str(dst).replace("\\", "/"),
                      "frames": len(kept), "height": canvas_h, "covered": round(covered, 2)})

    lines = ["# 整页拼接结果", ""]
    for i, it in enumerate(index, 1):
        if it.get("file"):
            lines.append(f"{i}. `{it['file']}` — {it['frames']} 帧，高 {it['height']}px，"
                         f"覆盖约 {int(it['covered']*100)}%｜{it['page'][:90]}")
        else:
            lines.append(f"{i}. 跳过（{it['note']}）｜{it['page'][:90]}")
    (out / "pages.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: python stitch.py <capture目录> [输出目录] [solid|mosaic|blur]")
    stitch(sys.argv[1],
           sys.argv[2] if len(sys.argv) > 2 else "pages",
           sys.argv[3] if len(sys.argv) > 3 else "solid")
