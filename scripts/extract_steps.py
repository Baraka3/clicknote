# -*- coding: utf-8 -*-
"""
视频 -> 步骤候选帧
核心思路: 步骤 = 界面静止下来的那一刻。
  1. 抽帧(4fps) -> 2. 计算相邻帧"变化像素占比" -> 3. 识别稳定段(连续低变化)
  -> 4. 每个稳定段取末帧作为快照 -> 5. 仅当快照与上一张已采纳帧差异够大才采纳
输出: frames/ candidates/ contact_sheet.jpg steps.json diag.json
"""
import json, re, subprocess, sys, shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()


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


def ffmpeg_probe(path):
    p = subprocess.run([FF, "-i", str(path)], capture_output=True, text=True)
    w = h = 0
    dur = 0.0
    for line in p.stderr.splitlines():
        if "Video:" in line and w == 0:
            m = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
        if "Duration:" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            hh, mm, ss = t.split(":")
            dur = int(hh) * 3600 + int(mm) * 60 + float(ss)
    return w, h, dur


def extract_frames(video, outdir, fps, max_width):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("*.png"):
        f.unlink()
    vf = f"fps={fps}" + (f",scale='min({max_width},iw)':-2" if max_width else "")
    cmd = [FF, "-y", "-i", str(video), "-vf", vf, "-compression_level", "6",
           str(outdir / "f%06d.png")]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-1500:])
        raise SystemExit("抽帧失败")
    return sorted(outdir.glob("*.png"))


def thumb(path, width=400):
    img = Image.open(path).convert("L")
    if img.width > width:
        img = img.resize((width, max(1, round(img.height * width / img.width))), Image.BILINEAR)
    return np.asarray(img, dtype=np.float32)


def change_ratio(a, b, pix_tol=6.0):
    """两帧之间"明显变化的像素"占比。局部修改也能被捕捉，不被大片静止区稀释。"""
    if a.shape != b.shape:
        return 1.0
    return float((np.abs(a - b) > pix_tol).mean())


def block_peak(a, b, grid=8):
    if a.shape != b.shape:
        return 255.0
    diff = np.abs(a - b)
    h, w = diff.shape
    gh, gw = max(1, h // grid), max(1, w // grid)
    vals = [diff[i * gh:(i + 1) * gh, j * gw:(j + 1) * gw].mean()
            for i in range(grid) for j in range(grid)
            if diff[i * gh:(i + 1) * gh, j * gw:(j + 1) * gw].size]
    return float(np.percentile(vals, 95)) if vals else 0.0


def dhash(path, hs=8):
    g = Image.open(path).convert("L").resize((hs + 1, hs), Image.LANCZOS)
    a = np.asarray(g, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()


def ham(a, b):
    return int((a != b).sum())


def is_flat(path, tol=2.5):
    a = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    return float(a.std()) < tol


def detect(video, workdir, fps=4, max_width=1280,
           stable_th=0.0006, min_stable=2,
           step_ratio_th=0.0025, step_pmax_th=7.0, dedup_ham=8, verbose=True):
    frames = extract_frames(video, workdir / "frames", fps, max_width)
    n = len(frames)

    # 流式计算相邻帧变化占比（不常驻内存）
    ratios = np.zeros(n, dtype=np.float32)
    prev = None
    for i, p in enumerate(frames):
        cur = thumb(p)
        if prev is not None:
            ratios[i] = change_ratio(prev, cur)
        prev = cur

    stable = ratios < stable_th

    # 稳定段 -> 取段末帧
    snapshots = []
    i = 1
    while i < n:
        if stable[i]:
            j = i
            while j + 1 < n and stable[j + 1]:
                j += 1
            if j - i + 1 >= min_stable:
                snapshots.append(j)
            i = j + 1
        else:
            i += 1
    if not snapshots:
        snapshots = [n - 1]

    # 首帧纳入候选（视频起始状态）
    ordered = [0] + [s for s in snapshots if s > 0]

    # 步进筛选：与上一张已采纳帧差异够大才采纳
    accepted, hashes = [], []
    for k in ordered:
        p = frames[k]
        if is_flat(p):
            continue
        h = dhash(p)
        if not accepted:
            accepted.append(k)
            hashes.append(h)
            continue
        last = frames[accepted[-1]]
        thr = max(1, int(len(ratios) * 0))
        r = change_ratio(thumb(last), thumb(p))
        pm = block_peak(thumb(last), thumb(p))
        if r > step_ratio_th or pm > step_pmax_th:
            if hashes and ham(h, hashes[-1]) <= dedup_ham and r < 0.01:
                continue
            accepted.append(k)
            hashes.append(h)
        elif ham(h, hashes[-1]) > 30:  # 视觉差异大但像素比小（如小范围文字变化）
            accepted.append(k)
            hashes.append(h)

    # 导出
    cdir = workdir / "candidates"
    if cdir.exists():
        shutil.rmtree(cdir)
    cdir.mkdir(parents=True)
    steps = []
    for idx, k in enumerate(accepted, 1):
        dst = cdir / f"step{idx:02d}.png"
        shutil.copy(frames[k], dst)
        steps.append({"index": idx, "frame_no": k, "t": round(k / fps, 2),
                      "file": str(dst), "title": "", "body": "",
                      "redact": [], "highlight": []})
    (workdir / "steps.json").write_text(
        json.dumps({"source": str(video), "fps": fps, "steps": steps},
                   ensure_ascii=False, indent=2), encoding="utf-8")
    diag = {"frames": n, "fps": fps, "duration": round(n / fps, 2),
            "stable_runs": snapshots, "accepted": accepted,
            "ratio": [round(float(x), 5) for x in ratios]}
    (workdir / "diag.json").write_text(json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")
    make_sheet(cdir, workdir / "contact_sheet.jpg")
    if verbose:
        print(f"帧数={n} 时长={n/fps:.1f}s 稳定段={len(snapshots)} 采纳={len(accepted)}")
        print("变化占比曲线:", diag["ratio"])
    return steps, diag


def make_sheet(cdir, dst, cols=4, tw=340):
    imgs = sorted(cdir.glob("step*.png"))
    if not imgs:
        return
    s0 = Image.open(imgs[0])
    th = int(tw * s0.height / s0.width)
    rows = (len(imgs) + cols - 1) // cols
    pad, top = 10, 24
    W = cols * tw + (cols + 1) * pad
    H = rows * (th + top) + (rows + 1) * pad
    sheet = Image.new("RGB", (W, H), "#EEF1F5")
    d = ImageDraw.Draw(sheet)
    font = jfont(14, True)
    for i, p in enumerate(imgs):
        r, c = divmod(i, cols)
        x = pad + c * (tw + pad)
        y = pad + r * (th + top + pad)
        d.text((x + 2, y + 3), f"#{i+1}", font=font, fill="#1D4ED8")
        sheet.paste(Image.open(p).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y + top))
        d.rectangle([x, y + top, x + tw, y + top + th], outline="#94A3B8")
    sheet.save(dst, quality=85)
    print(f"对照图 -> {dst}  ({len(imgs)} 帧)")


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--probe" in sys.argv:
        if not argv:
            raise SystemExit("用法: extract_steps.py --probe <video>")
        w, h, dur = ffmpeg_probe(Path(argv[0]))
        print(json.dumps({"width": w, "height": h, "duration": round(dur, 2),
                          "orientation": "竖屏" if h > w else "横屏"}, ensure_ascii=False))
        raise SystemExit(0)

    video = Path(argv[0] if argv else "demo_register.mp4")
    work = Path(argv[1] if len(argv) > 1 else "work")
    work.mkdir(parents=True, exist_ok=True)
    w, h, dur = ffmpeg_probe(video)
    print(f"视频 {w}x{h} {dur:.1f}s")
    steps, diag = detect(video, work)
    print(f"\n提取 {len(steps)} 步:")
    for s in steps:
        print(f"  #{s['index']}  t={s['t']:>6}s  frame={s['frame_no']}")
