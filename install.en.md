# Install Clicknote (instructions for an AI assistant)

You are setting up Clicknote for a user. It is a Chrome extension plus a set of Python scripts that turn browser workflows into tutorial source material.

Work through the steps in order. Each one has a verification step. **Only stop for the user when something requires clicking inside the browser**; do everything else yourself.

---

## 0. Prerequisites

Check three things first. Fix whichever is missing before continuing.

```bash
python --version     # needs 3.9 or newer
python -c "import PIL; print(PIL.__version__)"   # needs Pillow
```

- Python below 3.9: ask the user to upgrade. Do not try to work around it.
- No Pillow: `pip install pillow` (if permissions fail, `pip install --user pillow`).
- On Windows where `python` is not recognised, try `py -3`, then `python3`.

Then confirm the browser: the user needs Chrome, Edge, or another Chromium-based browser, version 102 or newer (the extension uses Manifest V3). **Firefox is not supported** — do not attempt it.

## 1. Get the code

```bash
git clone https://github.com/Baraka3/clicknote.git
cd clicknote
```

Without git, have the user download the ZIP from the repository page — the result is identical.

Verify: `ls clicknote/extension/manifest.json` lists a file.

## 2. Install dependencies

```bash
pip install pillow
```

Pillow is the only dependency. Everything else uses the standard library. Do not pull in numpy or opencv.

Verify:

```bash
python scripts/import_capture.py 2>&1 | head -3
```

A `usage` message or "no steps found" means it ran. A `ModuleNotFoundError` means the wrong interpreter.

## 3. Install the browser extension

**The user has to do this part. Read the steps to them, then wait for confirmation.**

Ask the user to:

1. Open `chrome://extensions` (Edge: `edge://extensions`)
2. Turn on **Developer mode** in the top right
3. Click **Load unpacked** in the top left
4. Select `<repo path>/extension` — the directory that contains `manifest.json`, not the repository root
5. A blue icon appears in the toolbar; pin it via the puzzle-piece menu

Wait until the user confirms before continuing.

## 4. Self-check

Run the bundled example to confirm the pipeline works end to end:

```bash
python scripts/import_capture.py examples/minimal/capture.json .tmp-check
python scripts/render.py .tmp-check/steps.json .tmp-check/out
ls .tmp-check/out/images | head
```

Expected: `.tmp-check/out/` contains `tutorial.md`, `tutorial.html`, and `images/step01.png`.

On success, delete `.tmp-check` and tell the user it is installed, then hand them the workflow:

> Open the page you want to document → click the extension icon → Start capture → do the task → Stop → Export. Send me the JSON path.

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `Load unpacked` throws an error | Wrong directory selected | Point at `extension/`, the one containing `manifest.json` |
| Extension installed but the counter stays at 0 | Current page is `chrome://` or the extension store | Internal pages cannot be injected; use a normal web page |
| `ModuleNotFoundError: PIL` | Pillow went to a different Python | `python -m pip install pillow`, and make sure you run scripts with the same interpreter |
| Exported JSON has an empty `actions` array | No click or input happened during capture | Check that Start capture was pressed, and that navigation stayed on the starting domain (domain lock ignores other sites) |
| `stitch.py` says no `scrollY` | Capture came from extension 1.0.0 | Re-capture. Old captures have no scroll position; refusing is correct behaviour, not a bug |

## Boundaries

- Do not patch `extension/` to work around an environment problem. Diagnose first.
- Do not touch the user's other browser extensions without asking.
- Captured screenshots contain the user's private data. **Never upload them anywhere.** Reporting file paths is enough.
