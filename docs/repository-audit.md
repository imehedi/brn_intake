# Repository maintenance review

Reviewed 31 October 2026. Scope: both shell launchers, all first-party Python and inline browser JavaScript, prompts/configuration, Docker/Compose, documentation and vendored assets. This is a static maintenance review with frontend browser checks; the external vault and Ollama were unavailable for end-to-end validation.

## Obsolete scripts

No standalone script is demonstrably obsolete. Retain these entry points:

| File or path | Evidence and recommendation |
|---|---|
| `bin/brain-intake` | README's primary Docker launcher; manages signing keys, people-store initialization, Compose, readiness and shutdown. Keep. |
| `bin/run-native.sh` | Documented native fallback that executes the same server. Keep; its Mac-specific interpreter search is intentional. It does not reproduce the container's network isolation or signing setup. |
| `app/server.py` | Container and native entry point. Its `--extract` mode is called by `extract_isolated`, so it is an active subprocess interface, not an old CLI. Keep. |
| `app/rag.py` | Imported by the server for indexing, retrieval and citation checks. Keep. |
| `relay/relay.py` | Compose's second service; enforces Ollama route/model restrictions. Keep even though native mode does not use it. |
| Files/Chat/Inbox screens | Still reachable from Menu and backed by active API handlers. Their review workflows differ from automatic intake. Do not remove solely because Search is now the default screen. |
| Prompts and vendored d3/fonts | Referenced by server/UI; vendoring supports local operation and the restrictive content security policy. Keep. |

Removed two unused CSS selectors (`ask-row`, `ask-input`) and the permanently hidden duplicate landing introduction. Updated stale landing references to the renamed Save thought action.

## Follow-up findings

| Finding | Impact and recommended action |
|---|---|
| arm64-specific dependency hashes | A hash-enforced install on this x86-64/Python 3.12 machine fails at `charset-normalizer==3.4.7`. README documents Apple silicon support. Add separately verified wheels/platform support in a dedicated dependency change if Linux x86-64 development is required; do not disable hash checks. |
| External vault is executable application dependency | Server startup requires the vault's `_system/scripts/brain.py`; commit gates and people commands also come from that vault. No portable development fixture or public setup path is included. Document/provide an approved development vault before claiming independent reproducibility. |
| Mac-specific launcher | `open`, Docker Desktop startup, macOS interpreter paths, `lsof`, and `host.docker.internal` assume the documented Mac workflow. These are platform restrictions, not evidence of obsolete scripts. |
| Build command invokes `prepare()` | Even `bin/brain-intake build` needs a real vault and can initialize a people store/signing settings. Consider separating build prerequisites from runtime initialization in a future launcher change. |
| Dormant cloud provider branches | Config retains Anthropic/OpenAI handlers and Keychain helpers while `allow_cloud` is false. Reachable behind configuration; not safely classifiable as dead code. Removing cloud support should be an explicit product decision with coordinated server/config/UI/docs changes. |
| No prior automated test suite or CI | Added `tests/check_landing.py` for frontend behavior with mocked APIs. Backend extraction, queue recovery, gate refusal/rollback and relay restrictions still need dedicated integration tests. |
| Large server and single-file frontend | Server mixes extraction, queueing, writes, retrieval and HTTP handling; HTML embeds extensive CSS/JS. Future modularization could improve maintenance, but avoid mixing a broad rewrite into a landing-page refresh. |

## Validation

`node --check` on the extracted inline script and `sh -n bin/brain-intake bin/run-native.sh` pass. `tests/check_landing.py` checks desktop/mobile light/dark layouts, horizontal overflow, default exclusion of client notes, suggestion behavior, live results, answer submission with scope flags, clear/reset, client-material saving, file chooser and Activity navigation, and fails on uncaught page errors.

Run with a Python environment containing Playwright and an installed Chromium:

```sh
python3 tests/check_landing.py
# Optional: select another Chromium installation
CHROMIUM_PATH=/path/to/chromium python3 tests/check_landing.py
```

The browser API is mocked explicitly. These checks validate frontend contracts, not real vault writes or model output. Screenshots are written to the system temporary directory. Full application startup remains blocked here by the missing vault/model service and incompatible dependency hashes.
