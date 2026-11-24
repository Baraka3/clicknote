# -*- coding: utf-8 -*-
"""
把浏览器扩展导出的 JSON 解码成可渲染的素材
输入: tutorial-capture-*.json（扩展导出的单文件）
输出:
  <outdir>/shots/stepNN.png    操作步骤截图（进教程）
  <outdir>/shots/scrollNN.png  滚动补采截图（不进教程，用于拼整页）
  <outdir>/steps.json          可直接喂 render.py
  <outdir>/pages.json          按页面分组的帧清单（含 scrollY），供 stitch.py 拼长图

用法: python import_capture.py <capture.json> [outdir]
"""
import base64, json, sys
from pathlib import Path


def import_capture(json_path, outdir="capture"):
    src = Path(json_path)
    data = json.loads(src.read_text(encoding="utf-8"))
    actions = data.get("actions", [])
    if not actions:
        raise SystemExit("JSON 里没有可用的步骤（actions 为空）")

    out = Path(outdir)
    shots = out / "shots"
    shots.mkdir(parents=True, exist_ok=True)
    for f in list(shots.glob("*.png")):
        f.unlink()

    steps, scrolls = [], []
    n_step = n_scroll = 0
    for a in actions:
        shot = a.get("shot") or ""
        if "," not in shot:
            continue
        kind = a.get("kind") or ""
        is_scroll = kind == "scroll"
        if is_scroll:
            n_scroll += 1
            dst = shots / f"scroll{n_scroll:02d}.png"
        else:
            n_step += 1
            dst = shots / f"step{n_step:02d}.png"
        dst.write_bytes(base64.b64decode(shot.split(",", 1)[1]))

        rec = {
            "file": str(dst).replace("\\", "/"),
            "kind": kind,
            "text": a.get("text") or "",
            "page": a.get("page_url") or "",
            "scroll_y": a.get("scrollY"),
            "doc_h": a.get("docH"),
            "box": a.get("box"),
            "redact": a.get("redact") or [],
        }
        if is_scroll:
            scrolls.append(rec)
            continue

        box = a.get("box") or {}
        highlight = [[box["x"], box["y"], box["w"], box["h"]]] if box else []
        steps.append({
            "index": n_step,
            "title": "",
            "body": "",
            "file": rec["file"],
            "redact": rec["redact"],
            "highlight": highlight,
            "notes": [],
            "_kind": kind,
            "_text": rec["text"],
            "_page": rec["page"],
            "page": rec["page"],
            "_scroll_y": rec["scroll_y"],
            "_doc_h": rec["doc_h"],
            "scroll_y": rec["scroll_y"],
            "doc_h": rec["doc_h"],
        })

    # 按页面归组：拼接整页长图时，同一 page_url 的帧才可能拼在一起
    pages = {}
    for rec in steps + scrolls:
        key = rec.get("page") or rec.get("_page") or ""
        pages.setdefault(key, []).append(rec)

    doc = {
        "doc": {
            "title": "（待填写）操作教程",
            "intro": "",
            "meta": "适用：网页端",
            "outro": "本文截图中的账号信息已做脱敏处理。",
        },
        "steps": steps,
    }
    (out / "steps.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "pages.json").write_text(json.dumps(pages, ensure_ascii=False, indent=2), encoding="utf-8")

    dropped = data.get("dropped", 0)
    no_pos = sum(1 for r in steps + scrolls if r["scroll_y"] is None)
    print(f"导入 {n_step} 步 + {n_scroll} 张滚动补采 -> {out/'steps.json'}")
    print(f"  截图目录: {shots}")
    if dropped:
        print(f"  （导出时因截图限速丢弃 {dropped} 步）")
    src_pages = data.get("pages") or []
    if src_pages:
        print(f"  来源页面: {src_pages[0]}" + (f" 等 {len(src_pages)} 个" if len(src_pages) > 1 else ""))
    if no_pos:
        print(f"  ⚠ {no_pos} 帧没有 scrollY（旧版扩展导出），整页拼接不可用")
    else:
        print("  已记录每帧 scrollY，可运行 stitch.py 拼整页长图")
    print("\n下一步：补写每步 title / body，再运行 render.py")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("用法: python import_capture.py <capture.json> [outdir]")
    import_capture(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "capture")
