# Brain Intake

The machinery around the second brain at `/opt/brain`, run as a container: intake of dropped files and chat messages, analysis by a local model, search, cited answers and the vault graph. The notes stay on the Mac, in the vault. This repository holds only the code that works on them.

```
 browser ──127.0.0.1:8765──▶ relay ──internal network──▶ app ──/vault──▶ /opt/brain (bind mount)
                               │                          │
                               │◀──── ollama.internal ────┘
                               └──▶ host.docker.internal:11434 ──▶ Ollama on the Mac (Apple GPU)
```

## Start it

```sh
/opt/git/brain-intake/bin/brain-intake up --open
```

The first run builds the image (about a minute) and creates two keys in `state/`: Brain Intake's own commit-signing key, and the access key the page needs. After that, `up` takes a few seconds and starts Docker Desktop if it isn't running. `open` opens the page with its key; the browser then keeps the key, so a bookmark to `http://127.0.0.1:8765` works afterwards.

| Command | What it does |
|---|---|
| `bin/brain-intake up [--open]` | Build (cached, so fast when nothing changed), start, and wait until the page answers |
| `bin/brain-intake open` | Open the page with its access key |
| `bin/brain-intake down` | Stop and remove the containers. The vault and `state/` are untouched |
| `bin/brain-intake restart` | Restart both containers |
| `bin/brain-intake build` | Rebuild the image without starting it |
| `bin/brain-intake logs` | Follow the logs |
| `bin/brain-intake status` | Containers, health, the page, the container clock and any git lock |
| `bin/run-native.sh [--open]` | Fallback without Docker: the same app and state, run on the Mac directly |

**Models.** They run in Ollama on the Mac, not in the container, because containers on macOS cannot use the Apple GPU. Extraction uses `gemma3:27b`; the decision model `jan-v1:4b` decides who is a person you know, where each note belongs and what a typed instruction asks for; Ask uses `embeddinggemma` for meaning search and `gemma3:4b` for answers. The Settings screen swaps any of them for another installed model. [docs/usage.md](docs/usage.md) says how to install them and how a drop is decided, filed and undone.

## How it is put together

- **Two containers from one image.** `app` runs the server. `relay` is a small forwarder and filter, and the only thing with a network route.
- **The app has no route out.** It sits on a Docker network marked `internal`. From inside it, internet names do not resolve, raw IP addresses are unreachable, and so is the Mac. Cloud processing cannot leave the Mac, whatever `allow_cloud` says.
- **The relay serves two fixed routes and nothing else:**
  - The page: a plain forward, which Docker publishes on the Mac's `127.0.0.1` only.
  - Ollama: an HTTP filter, not a pipe, because Ollama itself can reach the internet (pull, push, cloud models) and can delete models. It passes `GET /api/tags`, plus `POST /api/chat` and `POST /api/embed` naming a model that is installed on the Mac and runs there. Everything else is refused. The app reaches it as `ollama.internal`, because Ollama accepts only local-looking host names.
- **The vault is mounted, not copied, and its executable parts are read-only.** The app writes notes, sources, hubs and the archive. Mounted read-only over the vault, so a compromised file reader cannot plant code that runs later on the Mac:
  - `.git/config` and `.git/hooks`;
  - the gate (`_system/hooks`, `_system/scripts`);
  - `.obsidian`.

  Every commit runs the vault's own gate (`core.hooksPath` is forced in the container's environment). The gate's code is loaded from the vault, so the app and your own commits apply the same rules.
- **Commits are signed, but not with your key.** You are the author. Brain Intake is the committer and signs with its own SSH key in `state/signing/`. The launcher registers that key in the vault's `.git/config` (`gpg.ssh.allowedSignersFile`), so `git log --show-signature` on the Mac shows the signature as good. Your GPG key never enters a container. To revoke the key, delete its line from `state/signing/allowed_signers`.
- **An access key guards the API.** The key lives in `state/access.key` (0600) and never comes from the server: `open` puts it in the URL fragment, which the browser sends nowhere, and the page keeps it in local storage. Another container or local process that fetches the page still cannot use the API. The Host, Origin and same-site checks stay, for browsers.
- **Working state** lives in `state/` (git-ignored, private to your user): the FIFO queue (`queue.sqlite`), extraction jobs, chats, the search vectors, your model choices (`settings.json`), both keys, and `tmp/`, where the commit gate exports the vault for checking. That keeps it on disk, not in the container's memory.
- **A durable FIFO queue, not a broker.** Each addition is written to SQLite in `state/` before the page answers. One committer drains it oldest first and resumes after a restart. There is no extra container, no network and no extra memory.
- **Hardening:**
  - both containers run read-only, as non-root, with every Linux capability dropped and `no-new-privileges`, under memory and process limits;
  - the app runs as your Mac user;
  - stopping waits up to 60 s for a commit or its rollback to finish;
  - if a rollback ever fails, writes pause until someone looks;
  - a `.git/index.lock` held by the Mac's git is waited out for up to 10 s.
- **Supply chain:**
  - The base image is pinned by digest.
  - Every Python package is pinned to the version on the Mac, with the hash of its Linux arm64 wheel (`pip --require-hashes --only-binary=:all:`), so a substituted package fails the build. The image therefore builds on Apple silicon only.
  - The four Debian packages (`git`, `openssh-client`, `antiword`, `tzdata`) take current security updates within the pinned release, so two builds a month apart can differ there.
- **Each project gets its own image tag** (`brain-intake:<project>`), so a test build never replaces the image the real one runs.

## Settings

`bin/brain-intake` reads these from the environment. All are optional.

| Variable | Default | Meaning |
|---|---|---|
| `BRAIN_VAULT_HOST` | `/opt/brain` | The vault to mount |
| `BRAIN_PORT` | `8765` | The port on the Mac's `127.0.0.1` |
| `BRAIN_STATE_HOST` | `<repo>/state` | Jobs, chats and vectors |
| `BRAIN_PROJECT` | `brain-intake` | Docker project name; a second one can run side by side |

Your git name and email, your time zone and your user ID are read from the Mac at start-up.

**Docker Desktop must share both folders** under Settings → Resources → File sharing: `/opt/brain` and `/opt/git`. Mounts never create a missing folder, so a missing share stops the start rather than giving the app an empty vault.

**Test run:** a clone of the vault on port 8799, with its own state, leaves the real vault untouched:

```sh
git clone -q /opt/brain .test/vault && git -C .test/vault config core.hooksPath _system/hooks
BRAIN_VAULT_HOST=$PWD/.test/vault BRAIN_PORT=8799 BRAIN_STATE_HOST=$PWD/.test/state \
  BRAIN_PROJECT=brain-intake-test bin/brain-intake up
```

## Files

| Path | Purpose |
|---|---|
| `app/server.py` | The server: extraction, model calls, checks, vault writes, search and answer endpoints |
| `app/rag.py` | Local retrieval: chunking, keyword and meaning search, answer prompt, citation check |
| `app/static/` | The page (MH3 brand), its fonts and the vendored d3-force bundle |
| `app/prompts/` | Instructions for the models: extraction (`extract.txt`, `extract-research.txt`), filing decisions (`decide.txt`), people (`people.txt`) and typed instructions (`update.txt`) |
| `app/config.json` | Models, limits and the data boundary (`allow_cloud: false`) |
| `relay/relay.py` | The relay: a plain forward for the page and an allowlist filter for Ollama |
| `Dockerfile`, `compose.yaml`, `requirements.txt` | The image, the two services and the pinned dependencies |
| `bin/` | The launcher and the native fallback |
| `docs/usage.md` | How to use the page: Chat, Ask, Files, Inbox, Graph |

History before 29 October 2026 comes from `_system/intake/` in the vault and was split out with `git subtree`, so `git log` shows the whole story.

---

Built with AI assistance (Claude), reviewed and directed by Mehedi Hassan.
