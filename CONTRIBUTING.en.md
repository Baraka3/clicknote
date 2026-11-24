# Contributing

Before opening an issue, check the [known limits](README.en.md#known-limits) — several of them are deliberate trade-offs, not bugs.

## Welcome

- **New redaction criteria** — hit a sensitive field type we don't cover? Explain *why this value can narrow down to a specific person*.
- **Alternative capture implementations** — producing the same JSON from Playwright, Puppeteer or a test framework. These PRs are the most valuable.
- **Layout and typography** — there is currently one default style. We need more: long-form WeChat posts, internal wikis, PDF.
- **Documentation fixes** — typos, unclear passages. Just fix them.

## Not accepted

- Turning this into a SaaS (adding a backend, accounts, a database). Local-first is the line.
- Introducing a bundler. The extension is deliberately plain JS — source files *are* the loadable files, edit and hit refresh.
- Replacing DOM coordinates with image recognition. Accuracy drops and redaction starts missing things.

## Code style

- Extension: ES5-flavoured syntax (`function`, not arrow functions), no third-party libraries.
- Python: Pillow is the only dependency, everything else is stdlib. One file solves one problem — no speculative abstraction.

## Pull requests

1. One PR does one thing.
2. Changed rendering logic: include a before/after image.
3. Changed capture logic: describe how you verified it (which site, what actions).

## Reporting a capture bug

All of this is needed; missing any one makes it unreproducible:

- Browser and version
- The page URL (if confidential, describe the structure instead — "single-page form", "multi-step wizard")
- The failing frame's `kind`, `scrollY`, `viewport` from the exported JSON (screenshots optional)
- What happened vs what you expected

---

中文贡献指南见 [CONTRIBUTING.md](CONTRIBUTING.md)。
