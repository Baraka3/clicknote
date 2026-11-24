# Clicknote

**Record browser workflows as raw material. Let an AI write the tutorial.**

A Chrome extension captures clicks, screenshots, scroll positions and sensitive-field bounds. A small Python toolchain turns that into redacted, annotated, version-controllable tutorials. A skill spec tells the AI which frame counts as a step, what the copy should say, and what must be redacted.

*[中文说明见 README.md](README.md)*

---

## This is not another screenshot recorder

[Scribe](https://scribehow.com), [Tango](https://tango.us) and [Mimik](https://github.com/westpoint-io/mimik) all solve "record once, get a document". Their copy is template-filled — editable in theory, slower to fix than to rewrite.

Clicknote takes the other path: **capture precisely, let the AI judge.**

| | Template-based tools | Clicknote |
|---|---|---|
| Which frame is a step | rules | AI, against a written spec |
| Who writes the copy | templates | AI in your project's voice, or you |
| Redaction | keyword matching | per-value judgement, coordinates from DOM |
| Output | finished document | intermediate JSON + steps.json, rewritable |
| Prerequisite | install and go | an AI assistant that can read files and run commands |

The trade-off is honest: **it does not work out of the box.** You need Claude Code, Cursor, WorkBuddy or similar. If you just want a PDF at the end of a recording, use Mimik instead.

## Why the coordinates are accurate

Most tools locate elements via image recognition — off by pixels to tens of pixels. Here the box comes straight from `getBoundingClientRect()`, sub-pixel accurate, so highlight frames sit exactly on the button.

Redaction works the same way: DOM bounds, not OCR. Nothing gets half-covered, nothing adjacent gets blurred by accident.

## Workflow

```
1. Install extension → start capture → do the task → export JSON
2. python scripts/import_capture.py capture.json capture
3. Write each step's title and body (human or AI)
4. python scripts/render.py capture/steps.json out
   ↓
   images/step01.png … + tutorial.md + tutorial.html
```

Step 3 is where quality happens. The skill spec requires action titles ("Click submit", not "Submit page"), bodies that explain pitfalls rather than restate the screenshot, and no filler like "as you can see".

## Install

### Let an AI do it

Paste this into Claude Code / Cursor / WorkBuddy:

```
Install Clicknote for me. Read
https://raw.githubusercontent.com/<your-username>/clicknote/main/install.md
first, then install the extension and Python scripts, and run the self-check.
```

### Manually

```bash
git clone https://github.com/<your-username>/clicknote.git
cd clicknote
pip install pillow

# Chrome → chrome://extensions → enable Developer mode
# → Load unpacked → select the extension/ directory
```

## Capture format

```json
{
  "index": 12,
  "kind": "click",
  "text": "Place order",
  "box": { "x": 0.0625, "y": 0.8424, "w": 0.1688, "h": 0.0722 },
  "redact": [[0.0625, 0.2597, 0.4375, 0.0611]],
  "scrollY": 1284,
  "docH": 3106,
  "viewport": { "w": 1920, "h": 1031 },
  "shot": "data:image/png;base64,..."
}
```

Full field reference: [`docs/capture-format.md`](docs/capture-format.md).

## Redaction rule

The test is **"can this value narrow down to a specific person?"** — not what kind of input it is.

Redact: names, every part of an address (including state and ZIP), dates of birth, ID numbers, email, phone, job title, income, education, account details.

Safe to keep: shared category declarations such as employment status, citizenship, residency status — values millions of people hold.

Rationale and the mistakes we made getting there: [`docs/redaction-rules.md`](docs/redaction-rules.md).

## Known limits

1. Chrome caps screenshots at 2/second. Fast operations keep the record but lose the image.
2. Main document only — iframe interactions are not captured.
3. Hover pre-screenshots fire up to a few hundred ms before the click; if the page scrolled in between, the `box` will be off.
4. Scroll capture is not a full-page screenshot. Layout shifts mid-scroll (inline validation errors, expanded dropdowns) will misalign `stitch.py`. Old captures without `scrollY` are rejected outright rather than guessed.
5. An AI assistant is required for the copy.

## License

MIT.
