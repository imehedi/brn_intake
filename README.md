---
title: "README"
type: system
domain: system
status: evergreen
created: 2026-10-29
updated: 2026-10-29
summary: "Brain Intake: a local page where dropped material becomes reviewed draft notes, filed through the vault gate."
sensitivity: internal
tags: [system, intake]
---

# Brain Intake

A single page on `http://127.0.0.1:8765` where you drop material and keep the knowledge. It runs on this Mac and writes only to this vault.

## Start it

```sh
/opt/brain/_system/intake/start.sh --open
```

Leave the terminal open while you use it. Ollama must be running (`ollama serve`, or the Ollama app).

## What happens to a drop

1. **Read on this Mac.** PDF, Word, PowerPoint, Excel, HTML, RTF, ODT, Markdown, text, CSV and JSON are turned into text locally. Scanned PDFs need OCR first.
2. **Extracted by a local model.** `gemma3:27b` through Ollama by default; any installed Ollama model can be chosen. The model proposes atomic notes as JSON in the vault's own types, domains and house style, with quotations from the source.
3. **Checked.** Every quotation is checked word for word against the source text. Notes whose name already exists are blocked. Links are kept only when they point at real notes.
4. **Reviewed by you.** Edit the title, heading, type, domain, sensitivity, summary, body and tags. Untick anything not worth keeping.
5. **Saved to `00 Inbox/` in one commit**, with the original file, its extracted text and an `intake.json` record under `_sources/<year>/`. Notes are `status: draft` with `sources`, `extracted_by` and `confidence` in their frontmatter.
6. **Promoted from the Inbox tab.** One click moves the note into its domain folder (by type, for the two MOC domains), sets its status, links it from the hub and commits all three together through the vault gate. If the gate refuses, everything is put back.
7. **Archived, not deleted,** if you discard a draft: it moves to `_archive/<date>/intake-discarded/` and the day's `MANIFEST.md` records it.

## Data boundary

- `allow_cloud` in `config.json` is `false`. The server refuses every cloud call; the page cannot change that. The file is tracked, so any change to the boundary is in the git history.
- Client material is processed locally whatever the config says.
- Notes made from client material stay client: the page offers only the same or a stricter sensitivity.
- If cloud processing is ever enabled, Claude (`claude-sonnet-5-5`, with `claude-opus-5-5` as the deep option) is the default; OpenAI needs a model name in `config.json`. Keys are read from the macOS Keychain, never from the vault:

```sh
security add-generic-password -U -a "$USER" -s brain-intake-anthropic -w   # prompts for the key
security add-generic-password -U -a "$USER" -s brain-intake-openai -w
```

Only text extracted from the file would be sent, together with the titles of `internal` notes for linking.

## Safety

- Listens on `127.0.0.1` only, and refuses a request with a foreign Host or Origin header, a cross-site fetch, or a missing per-session token. A content security policy allows only the page's own script.
- A dropped document is treated as data. Its text is fenced in the prompt, the model's output is parsed as JSON and never executed, and the page renders every string as text.
- The server writes only to `00 Inbox/`, `_sources/`, hub notes on promotion and `_archive/`. It refuses to commit while you have other changes staged, or when the hub has uncommitted edits.
- Files are read in a separate process with a three-minute limit, and archives that would expand to an unsafe size are refused before they are opened.
- The local model is reached directly on `127.0.0.1`, never through a proxy, and Ollama models that run remotely are not offered.
- Model text is cleaned before it is saved: links that would not resolve become plain text, remote images and raw HTML are removed, and headings that would imitate the Evidence, Source or Related sections are relabelled.
- A hub never carries text more sensitive than itself. A client note promoted into an internal hub gets a bare link with no summary.
- A quotation counts as found only if it appears word for word, or as ordered fragments of 25 characters or more. Notes with no verified quotation start unticked.
- If a commit fails, for example because a signing prompt was dismissed, everything is put back, including the generated index.
- Uploads wait in `_system/intake/.work/` (git-ignored, private to your user) until saved. Clear removes that scratch copy.

## Files

| Path | Purpose |
|---|---|
| `server.py` | The local server: extraction, model calls, checks, vault writes |
| `static/index.html` | The page, in the MH3 studio brand |
| `prompts/extract.txt` | The extraction instructions given to the model |
| `config.json` | Port, models, limits and the data boundary |
| `start.sh` | Finds a suitable python3 and starts the server |
