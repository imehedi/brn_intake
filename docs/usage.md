---
title: "Brain Intake usage"
type: system
domain: system
status: evergreen
created: 2026-10-29
updated: 2026-10-30
summary: "Brain Intake: a local page where dropped material becomes reviewed draft notes, filed through the vault gate."
sensitivity: internal
tags: [system, intake]
---

# Brain Intake

A single page on `http://127.0.0.1:8765` where you drop material and keep the knowledge. It runs in a container on this Mac, with no route to the internet, and writes only to the vault at `/opt/brain`.

## Start it

```sh
/opt/git/brain-intake/bin/brain-intake up --open
```

It keeps running in Docker after the terminal closes; `bin/brain-intake down` stops it. Ollama must be running on the Mac (`ollama serve`, or the Ollama app). Without Docker, `bin/run-native.sh --open` runs the same app directly on the Mac.

## Search, ask and tell

The page opens on one box: a search engine over your own brain.
- **Typing** searches as you go, by keyword and by meaning.
- **Enter** asks: a short answer written only from your notes, every claim cited, with the matching notes beneath it. Client notes, inbox drafts and people stay out unless you tick them.
- **Cmd+Enter** / **Ctrl+Enter** (or **Save thought**) adds what you typed to the brain.
- **Dropping a file anywhere** on the page adds it. The paperclip does the same.

**Suggested searches** fill the search box without saving or asking automatically. **Clear search** returns to the landing page. Client notes, inbox drafts and people are excluded by default; their filters are always visible. **Save as client material** applies to new additions, separately from the search filters.

**Add files**, **Explore the graph** and **View activity** are available directly on the landing page. **Menu** holds Activity, Settings and the other screens. A small counter appears at the top only while something is being worked on or needs a look.

## The queue

Everything you add is written to a queue on disk (`state/queue.sqlite`) before the page says "Added", so you can keep adding while the committer works. One committer takes the oldest entry first, one at a time. Activity shows each one's place in the queue.

If Brain Intake or Docker restarts, whatever was waiting, or half done, is taken again in its original order:
- A drop that had already been committed is not committed twice.
- An instruction that had already changed something is not replayed.

## What happens to what you add

1. **Rules come first, with no model involved.**
   - A source with a DOI or arXiv identifier and an abstract or reference list is treated as a research paper.
   - A short line such as "CONFIDENTIAL" or "Commercial in confidence", or a client domain, makes the notes client. So does ticking **Client material**.
   - No model can lower these floors.
2. **The extraction model writes the notes**, with quotations checked word for word against the source.
3. **People join the register by themselves**, before any note is written, so every note names them by acronym.
   - The decision model judges each name it finds: someone you know, a public figure, an author or cited person of published work, or not a person.
   - Only people you know are added.
   - Authors, bylines, reference lists, in-text citations ("Smith et al. (2020)") and your own name are never added.
   - If it cannot tell, the person is added as *unsure*. A real name kept out of the vault by mistake costs one register row; one committed by mistake stays in git history.
   - **Not someone I know** in Activity archives the row and stops that name from being added again.
   - **Nothing is filed while a name is unresolved.** That covers a person who could not be added (the people store has edits of its own, say) and someone you know named by first name only. Activity shows **Waiting on these names**, with **Add to People** (you can complete the name) and **Not someone I know**, then **File again**. Typed text never lends its first line to a file name or commit message.
   - The person's log gets one locked observation from the source.
4. **The decision model decides each note.** It chooses where the note belongs, how sensitive it is (never below the floor), whether it repeats an existing note, and whether to file or hold it.
5. **A note is filed only when every check passes:**
   - the decision model says file;
   - its home agrees with the extraction model's, or clearly beats the runner-up by meaning;
   - every quotation is found in the source;
   - it is not an inference;
   - it is not too close to an existing note.

   Anything else waits under **Needs a look**, with the reason, and **File it** or **Discard** next to it. A paper's claims wait with its literature note.
6. **One signed commit per drop.** Filed notes go to their homes and hubs, held ones to `00 Inbox`, and the source to `_sources/`. **Undo** moves all of it into `_archive/<date>/intake-undone/` with manifest rows, and takes the hub links out. Nothing is deleted. Log entries stay, because they are locked; add a correction if one is wrong.

If the decision model is not installed or does not answer, nothing is guessed: every note waits for a look. The same file dropped twice is refused while its notes are in the vault.

**Typed instructions.** Typed text can also be an instruction rather than material, for example "FR is my wife, not my sister-in-law", "add to RAR's profile that…", "archive the note about Kubernetes operators" or "undo the last drop". The decision model turns it into operations from a fixed list:
- add to or set a profile;
- log an observation or a correction;
- change how you know someone;
- add or archive a person;
- replace exact text in a note;
- archive a note;
- undo a drop.

Each operation is checked against the real register, the notes the search found and your recent drops, and applied through the same gates.
- **Applied at once, with Undo changes:** adding to a profile and changing how you know someone, both reversible.
- **Wait for Apply** (an irreversible log entry or a change to a note): log entries, adding a person, replacing text in a note, archiving, undoing, and replacing a whole profile. So does any plan made from more than 500 characters, or with more than four changes.

Text is replaced only in a note's body, never its frontmatter, so sensitivity cannot be lowered from here. Hubs and maps of content are never archived. Files you drop are never read as instructions; only text you type is.

## Settings

Choose which installed model does each job:
- **Extraction:** the large model that reads sources.
- **Decisions:** the small judge.
- **Answers:** writes answers on the Ask screen.
- **Search embeddings:** must be an embedding model; changing it rebuilds the vectors.

Only models installed in Ollama on this Mac are offered; cloud models never are. Choices are kept in `state/settings.json` and override `config.json`, which is part of the image. **Use the defaults** goes back to `config.json`.

The decision model is `jan-v1:4b` (Jan-v1, 4B, built on Qwen3), fetched from Hugging Face:

```sh
ollama pull hf.co/janhq/Jan-v1-4B-GGUF:Q4_K_M && ollama cp hf.co/janhq/Jan-v1-4B-GGUF:Q4_K_M jan-v1:4b
```

## More

Chat, Ask, Files, Inbox, People, Research and Graph are one click away under **More**. They work as before. The Chat and Files paths also add new people to the register before drafts are made.

## Chat

The Chat tab is the quickest way in. Choose a sensitivity once per chat, then type or paste a message and press Enter. Each message is read by the local model on its own and comes back as draft notes, with the same quote checks, editing and one-click save to the inbox as files. The three previous messages go to the model as context only, so "the same applies to schema changes" is understood; drafts that merely restate an earlier message are left out and you are told so. A chat's sensitivity can be raised, never lowered, and raising it reaches drafts already extracted. Deleting a chat removes its unsaved drafts from this Mac; saved notes stay in the vault. Chats live in `state/chats/` in this repository (git-ignored, private to your user); a saved message becomes the note's source under `_sources/`.

## Graph

The Graph tab draws the vault the way Obsidian does: every note a node, every link an edge, coloured by domain, type, sensitivity, status or your Obsidian colour groups, in the brand's chart palette. Search, filter, show a note's local graph (one to three links out), add tags as nodes, switch on the health overlay (orphans, missing summaries, unverified drafts, broken links), replay the vault's growth on the timeline, and export the view as PNG or SVG. The side panel shows a note's summary, backlinks and links out, with Open in Obsidian. Client summaries stay hidden until you ask, and Client notes can be switched off before you share a screen. It reads the vault live on each refresh through the same parser as the commit gate; nothing is fetched from the internet.

## Ask your notes

The Ask tab answers questions in plain English from this vault, on this Mac.

**Set it up once:**

```sh
ollama pull embeddinggemma   # about 620 MB: lets search match meaning
ollama pull gemma3:4b        # about 3.3 GB: writes the answers
```

Keyword search works without either model. Without `embeddinggemma`, search matches words only. Without `gemma3:4b`, Ask shows the matching notes but writes no answer.

**How it finds notes.** Each note is split at its headings. A keyword ranking (BM25) is combined with a meaning ranking from `embeddinggemma`, then lightly boosted for notes linked to the best matches. No note contributes more than two sections. British and American spellings are treated as the same word, as are simple word forms: organisation and organizations, colour and colors, logging and log. Vectors are cached in `state/rag/` by content hash, so only new or changed sections are embedded. A background thread picks up edits within a few seconds.

**How it answers.** `gemma3:4b` sees only the top excerpts, fenced as data, and must cite one for every sentence. The page checks the citations. A number the model was not shown is struck through with a warning, and uncited sentences are counted. Clicking a citation shows its source. If you change the question afterwards, the old answer is dimmed, and clicking a citation brings back the sources it was written from.

**What it can see:**
- Only `internal` and `personal` notes, by default.
- Client and unlabelled notes, only when **Include client and unlabelled notes** is ticked. A note whose frontmatter cannot be read, or which repeats a key such as `sensitivity`, counts as unlabelled.
- Inbox drafts, only when **Include inbox drafts** is ticked.

The server applies these rules before ranking, and the page cannot widen them. Full section text never leaves the server; the page receives a snippet.

**Protecting the Mac:**
- One answer at a time; a second request is refused until the first finishes.
- An answer is capped at 600 tokens and 180 seconds.
- While an extraction is running on the large model, answers and embedding wait, and search carries on.
- Closing the page stops the model.
- If Ollama hangs, search falls back to keywords within three seconds.

| Setting in `app/config.json` → `rag` | Default | Meaning |
|---|---|---|
| `embed_model` | `embeddinggemma` | Embedding model for meaning search |
| `answer_model` | `gemma3:4b` | Model that writes answers |
| `k` | 6 | Excerpts given to the answer model |
| `num_ctx` / `num_predict` | 8192 / 600 | Context and answer length, in tokens |
| `min_similarity` | 0.3 | Floor for a meaning match |
| `reindex_seconds` | 120 | Longest wait before a background re-index |

## What happens to a drop

1. **Read on this Mac.** PDF, Word, PowerPoint, Excel, HTML, RTF, ODT, Markdown, text, CSV and JSON are turned into text locally, in the container. Scanned PDFs need OCR first. RTF, ODT, Safari web archives and old `.doc` files use the container's own readers rather than macOS `textutil`, so tables and footnotes in those formats come through more plainly.
2. **Extracted by a local model.** `gemma3:27b` through Ollama by default; any installed Ollama model can be chosen. The model proposes atomic notes as JSON in the vault's own types, domains and house style, with quotations from the source.
3. **Checked.** Every quotation is checked word for word against the source text. Notes whose name already exists are blocked. Links are kept only when they point at real notes.
4. **Reviewed by you.** Edit the title, heading, type, domain, sensitivity, summary, body and tags. Untick anything not worth keeping.
5. **Saved to `00 Inbox/` in one commit**, with the original file, its extracted text and an `intake.json` record under `_sources/<year>/`. Notes are `status: draft` with `sources`, `extracted_by` and `confidence` in their frontmatter.
6. **Promoted from the Inbox tab.** One click moves the note into its domain folder (by type, for the two MOC domains), sets its status, links it from the hub and commits all three together through the vault gate. If the gate refuses, everything is put back.
7. **Archived, not deleted,** if you discard a draft: it moves to `_archive/<date>/intake-discarded/` and the day's `MANIFEST.md` records it.

## Memory

The local model is large for this Mac. The server sizes the model's context window to each request (8k tokens for a chat message rather than 32k), and the model is unloaded five minutes after its last use (`keep_alive` in `app/config.json`). If the Mac slows down, close other large apps, or pick a smaller installed model such as `gpt-oss:20b` in the Files tab.

## Data boundary

- `allow_cloud` in `app/config.json` is `false`. The server refuses every cloud call; the page cannot change that. The file is tracked, so any change to the boundary is in the git history.
- In the container the boundary is also physical: the app has no route to the internet, so a cloud call cannot leave the Mac even if the config were changed. Cloud processing would need the native fallback.
- Client material is processed locally whatever the config says.
- Notes made from client material stay client: the page offers only the same or a stricter sensitivity.
- If cloud processing is ever enabled, Claude (`claude-sonnet-5-5`, with `claude-opus-5-5` as the deep option) is the default; OpenAI needs a model name in `app/config.json`. When run natively, keys are read from the macOS Keychain, never from the vault:

```sh
security add-generic-password -U -a "$USER" -s brain-intake-anthropic -w   # prompts for the key
security add-generic-password -U -a "$USER" -s brain-intake-openai -w
```

Only text extracted from the file would be sent, together with the titles of `internal` notes for linking.

## Safety

- Reachable on the Mac's `127.0.0.1` only, and refuses a request with a foreign Host or Origin header, a cross-site fetch, or a missing per-session token. A content security policy allows only the page's own script.
- A dropped document is treated as data. Its text is fenced in the prompt, the model's output is parsed as JSON and never executed, and the page renders every string as text.
- The server writes only to `00 Inbox/`, `_sources/`, hub notes on promotion and `_archive/`. It refuses to commit while you have other changes staged, or when the hub has uncommitted edits.
- Files are read in a separate process with a three-minute limit, and archives that would expand to an unsafe size are refused before they are opened.
- The local model is reached only through the fixed relay (`ollama.internal`) in the container, or on `127.0.0.1` natively, and Ollama models that run remotely are not offered.
- Model text is cleaned before it is saved: links that would not resolve become plain text, remote images and raw HTML are removed, and headings that would imitate the Evidence, Source or Related sections are relabelled.
- A hub never carries text more sensitive than itself. A client note promoted into an internal hub gets a bare link with no summary.
- A quotation counts as found only if it appears word for word, or as ordered fragments of 25 characters or more. Notes with no verified quotation start unticked.
- If a commit fails, for example because the gate refused it, everything is put back, including the generated index. If putting it back fails, writes pause until you have looked at `git status`.
- Uploads wait in `state/` (git-ignored, private to your user) until saved. Clear removes that scratch copy.

## Files

| Path | Purpose |
|---|---|
| `app/server.py` | The local server: extraction, model calls, checks, vault writes |
| `app/rag.py` | Local retrieval for the Ask tab: chunking, keyword and meaning search, answer prompt, citation check |
| `app/static/index.html` | The page, in the MH3 studio brand: Chat, Ask, Files, Inbox and Graph |
| `app/static/vendor/d3-force-bundle.js` | d3-force 3.0.0 and its three dependencies (ISC licence), stored locally |
| `app/prompts/extract.txt` | The extraction instructions given to the model |
| `app/config.json` | Port, models, limits and the data boundary |
| `bin/brain-intake` | Starts, stops and rebuilds the container; see the repository README |
| `bin/run-native.sh` | Runs the same app directly on the Mac, without Docker |
