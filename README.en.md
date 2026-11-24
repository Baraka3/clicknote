# Clicknote

[简体中文](README.md) | English

**Record browser workflows as raw material. Let an AI write the tutorial.**

- **Capture** — Chrome / Edge extension records clicks, typing and scrolling. Element boxes come from the DOM, not image recognition, so highlights land within 1px.
- **Render** — a small Python toolchain redacts, annotates and lays out the result as Markdown and a self-contained HTML file.
- **Judge** — `SKILL.md` defines what counts as a step, how a title should read, and what must be redacted.
- **Built for** — people who maintain a lot of how-to documentation and already work inside Claude Code / Cursor / WorkBuddy.

> **Maintenance mode.** Bug fixes and documentation corrections are welcome. New features are not scheduled. The value here is the judgement criteria, not the feature count.

---

## This is not another screenshot recorder

[Scribe](https://scribehow.com), [Tango](https://tango.us) and [Mimik](https://github.com/westpoint-io/mimik) are all good tools. They solve "record once, get a document". Their copy is template-filled — editable in theory, slower to fix than to rewrite from scratch.

Clicknote takes the other path: **capture precisely, let the AI judge.**

| | Template-based tools | Clicknote |
|---|---|---|
| Which frame counts as a step | rules | AI, against a written spec |
| Who writes the copy | templates | AI in your project's voice, or you |
| Redaction | keyword matching | per-value judgement, coordinates from the DOM |
| Output | finished document | intermediate JSON + `steps.json`, rewritable |
| Prerequisite | install and go | an AI assistant that can read files and run commands |

The trade-off is honest: **it does not work out of the box.** You need Claude Code, Cursor, WorkBuddy or similar. If all you want is a PDF at the end of a recording, use Mimik — not this.

## Why the coordinates are accurate

Most tools locate elements through image recognition, landing anywhere from a few pixels to tens of pixels off. Here the box comes straight from `getBoundingClientRect()`, so highlight frames sit exactly on the button instead of floating around it.

Redaction works the same way — DOM bounds, not OCR. Nothing gets half-covered, and nothing adjacent gets blurred by accident.

## Workflow

```
1. Install extension → start capture → do the task → export JSON
2. python scripts/import_capture.py capture.json capture
3. Write each step's title and body (human or AI)
4. python scripts/render.py capture/steps.json out
   ↓
   images/step01.png … + tutorial.md + tutorial.html
```

Step 3 is where quality happens. The skill spec requires action titles ("Click submit", not "Submit page"), bodies that explain pitfalls rather than restate the screenshot, and none of the "as you can see" filler.

## Install

### Let an AI do it

Paste this into Claude Code / Cursor / WorkBuddy:

```
Install Clicknote for me. Read
https://raw.githubusercontent.com/Baraka3/clicknote/main/install.en.md
first, then set up the browser extension and Python scripts, and run the self-check.
```

The assistant checks your environment, installs Pillow, and only stops when it needs you to click something in the browser.

### Manually

```bash
git clone https://github.com/Baraka3/clicknote.git
cd clicknote
pip install pillow

# Extension: open chrome://extensions → enable Developer mode
# → Load unpacked → select the clicknote/extension directory
```

Edge works the same way: `edge://extensions` → Developer mode → Load unpacked.

## Capture format

Each frame in the exported JSON looks like this:

```json
{
  "index": 12,
  "kind": "click",
  "tag": "button",
  "text": "Place order",
  "box": { "x": 0.0625, "y": 0.8424, "w": 0.1688, "h": 0.0722 },
  "redact": [[0.0625, 0.2597, 0.4375, 0.0611]],
  "scrollY": 480,
  "docH": 1180,
  "viewport": { "w": 1280, "h": 720 },
  "page_url": "https://demo.example.com/checkout",
  "shot": "data:image/png;base64,..."
}
```

`box` is the clicked element's normalised bounds. `redact` holds every sensitive input on screen. `scrollY` / `docH` let multiple frames of the same page be stitched into one full-page image. Full field reference: [`docs/capture-format.md`](docs/capture-format.md).

## Three capture-time behaviours

| Behaviour | What it solves |
|---|---|
| Domain lock | Wander off to check email mid-recording and it is ignored — unrelated browsing never enters the export |
| Scroll capture | Long pages have paragraphs with no clicks. Without this they simply go missing. A frame is taken 420 ms after scrolling stops, if the jump exceeded half a screen |
| Hover pre-shot | Clicking greys out or navigates away from what you wanted to show. A shot taken after 320 ms of hovering preserves the pre-click state |

## Redaction rule

The test is **"can this value narrow down to a specific person?"** — not what kind of input control holds it.

- **Redact** — names, every part of an address (including state and ZIP), dates of birth, ID numbers, email, phone, job title, income, education level, account details
- **Safe to keep** — shared category declarations such as employment status, citizenship, residency status. Values millions of people hold.

The reasoning, and the mistakes we made getting there, are in [`docs/redaction-rules.md`](docs/redaction-rules.md).

The short version of what we learned: **don't judge by "dropdown vs text field", judge by "does this value narrow things to one person".**

## Known limits

1. **Chrome caps screenshots at 2 per second.** Fast operations keep the record but lose the image. Leave 0.5 s between actions.
2. **Main document only** — iframe interactions are not captured.
3. **Hover pre-shots fire up to a few hundred ms before the click.** If the page scrolled in between, the `box` will not match the screenshot; verify highlight coordinates rather than trusting them blindly.
4. **Scroll capture is not a full-page screenshot.** It only adds frames where you paused. If the layout shifts mid-scroll (inline validation errors, a dropdown expanding), `stitch.py` output will be misaligned. Captures without `scrollY` are rejected outright rather than guessed at.
5. **An AI assistant is required** for the copy. Without one you write `steps.json` by hand.

## Repository layout

```
extension/          Chrome extension (Manifest V3, plain JS, no build step)
scripts/
  import_capture.py  JSON → shots/ + steps.json + pages.json
  render.py          redact, highlight, lay out → md + html
  stitch.py          stitch frames into a full-page image using scrollY
  extract_steps.py   frame extraction from video (if you'd rather not install the extension)
SKILL.md             the judgement spec handed to the AI — the core asset (written in Chinese;
                     the enforceable rules also appear in AGENTS.md and the Redaction rule above)
AGENTS.md            project conventions for AI coding assistants
llms.txt             structured index for LLM retrieval
docs/                capture protocol, redaction criteria
examples/minimal/    runnable example with fabricated data
```

## Contributing

See [CONTRIBUTING.en.md](CONTRIBUTING.en.md). Bug fixes and documentation corrections welcome; new features are not scheduled.

## License

MIT.
