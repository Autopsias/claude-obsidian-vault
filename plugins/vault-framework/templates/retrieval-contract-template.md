---
name: Retrieval Contract
description: Pinning record for Smart Connections — plugin version, embedding model, dimensions, vector-store index timestamp, rebuild procedure. Refresh when Smart Connections is updated, the model changes, or the index is rebuilt.
type: contract
cadence: monthly-or-on-structural-change
last_updated: "{{DATE}}"
provenance: Lifted from canonical Galp Vault implementation at scaffold time. Project-specific pinned values to be filled at first use.
---

<!-- PROJECT-SPECIFIC: Replace every {{PLACEHOLDER}} with your actual values.
     Run the verification procedure in ## M6 model-binary pin to compute the
     SHA-256. Run mcp__smart-connections__stats to get the indexed source count.
     See ## Rebuild procedure for the step sequence. -->

# Retrieval Contract — Smart Connections

This file is the pinning record for the vault's semantic retrieval substrate.
The five-step retrieval cascade documented in CLAUDE.md depends on Smart
Connections being at the version below, with the embedding model below,
embedding the dimensions below, and the .smart-env/ index being current.

## Pinned values

| Field | Value |
|-------|-------|
| Plugin | Smart Connections |
| Plugin version | `{{SC_PLUGIN_VERSION}}` |
| License | Smart Plugins License (post-Dec-2025; source-available with noncompete — review at each 6-month substrate review) |
| Embedding model | `{{EMBED_MODEL_KEY}}` |
| Embedding dimensions | {{EMBED_DIMS}} |
| Embedding runtime | `@huggingface/transformers` v4, WebGPU fp32 pipeline (Electron browser Cache API; fetches from HuggingFace CDN on first load, cached under key `"transformers-cache"`) |
| ONNX runtime | `{{ONNX_RUNTIME_VERSION}}` (loaded from jsDelivr CDN) |
| Vector store | `.smart-env/` (vault-internal; travels with the vault) |
| Index timestamp at pin | `{{INDEX_TIMESTAMP}}` (`.smart-env/` directory mtime at scaffold/migration) |
| Indexed source count at pin | {{SOURCE_COUNT}} (per `mcp__smart-connections__stats` at scaffold time) |

## M6 model-binary pin

SHA-256 and provenance of the actual ONNX model file served at embedding time.
Compute via Obsidian Electron DevTools `crypto.subtle.digest('SHA-256', ...)`.

| Field | Value |
|-------|-------|
| File | `onnx/model.onnx` (fp32 / WebGPU variant) |
| Source URL | `https://huggingface.co/{{EMBED_MODEL_KEY}}/resolve/main/onnx/model.onnx` |
| Size (bytes) | `{{MODEL_SIZE_BYTES}}` |
| SHA-256 | `{{MODEL_SHA256}}` |
| Cache location | Electron browser Cache API, cache key `"transformers-cache"` (no filesystem path; lives inside Obsidian's Electron app-data) |
| Verified by | Obsidian DevTools console (`Window > Toggle Developer Tools`); `caches.open("transformers-cache")` → `cache.match(url)` → `response.arrayBuffer()` → `crypto.subtle.digest("SHA-256", buf)` |
| Verified on | `{{DATE}}` |

### Why this pin matters

The runtime fetches the model from HuggingFace CDN on first load (no local bundle)
and stores it in the Electron browser Cache API. This means:
- The model file is **not** on the filesystem at any inspectable path; `find`/`ripgrep` will not locate it.
- A cache eviction, Obsidian reinstall, or OS clean-up of app Caches will silently wipe the cached binary, triggering a fresh CDN fetch — potentially a different model version.
- The SHA-256 above is the **currently pinned** binary. Rebaseline whenever Smart Connections is updated or if the vault health check detects embedding-quality regression.

### Rebaseline procedure (model-binary pin only)

1. Open Obsidian → `Window > Toggle Developer Tools` → **Console** tab.
2. Paste and run:
   ```js
   const url = "https://huggingface.co/{{EMBED_MODEL_KEY}}/resolve/main/onnx/model.onnx";
   const c = await caches.open("transformers-cache");
   const r = await c.match(url);
   const buf = await r.arrayBuffer();
   const hash = await crypto.subtle.digest("SHA-256", buf);
   const hex = Array.from(new Uint8Array(hash)).map(b=>b.toString(16).padStart(2,"0")).join("");
   console.log("size:", buf.byteLength, "sha256:", hex);
   ```
3. Update the `SHA-256` and `Size (bytes)` rows above, and bump `Verified on`.
4. Log to `99 Workspace/_auto_writes.md` with verb `edit` and reason "rebased model-binary pin after Smart Connections update".
5. If the hash has changed, run the M11 smoke-test (`python3 90 System/_smoke_test_retrieval.py`) and confirm pass before declaring retrieval healthy.

## Pin vs live state

The pin is set when the contract is written or rebuilt — see "Index timestamp
at pin" above. Smart Connections may report a more recent `last_updated` value
through `mcp__smart-connections__stats` during normal operation (incremental
re-embedding, plugin restart, vault edits). That divergence is expected and
does NOT trigger a re-pin. The pin refreshes only on explicit rebuild via the
procedure below.

<!-- PROJECT-SPECIFIC: Set the drift threshold appropriate for your vault's
     growth rate. The reference Galp implementation uses >2% as the re-embedding
     flag trigger in galp-vault-health. -->

A vault health check should compare live source count to the pinned count;
>{{DRIFT_THRESHOLD_PERCENT}}% drift is a re-embedding flag, not a re-pin trigger.

## M9 multilingual fall-through (if applicable)

<!-- PROJECT-SPECIFIC: The Galp Vault uses TaylorAI/bge-micro-v2, which degrades
     on Portuguese-heavy and Spanish↔Portuguese code-switched content. The five-step
     cascade explicitly bypasses step 1 (semantic) for those query languages.
     If your vault's primary language is English or uses a multilingual model,
     this section may be simplified or removed. -->

The pinned embedding model `{{EMBED_MODEL_KEY}}` has the following multilingual
behaviour documented in `90 System/_operating_guide.md` P-3:

```
[PROJECT-SPECIFIC: Document the model's known language limitations here.
 For bge-micro-v2: degrades on PT-heavy / ES↔PT code-switched content.
 The five-step cascade in CLAUDE.md/P-3 explicitly bypasses step 1 (semantic)
 for those query languages and falls through to step 2 (Bases) or step 0 (lexical).
 This is a known substrate limitation — do not attempt to fix by switching models
 without re-running the M2 eval and re-baselining the contract.]
```

## Rebuild procedure

If Smart Connections is updated, the model changes, the embedding count
diverges from the vault's markdown count by more than the drift threshold,
or the index becomes stale (whichever surfaces first via vault health check):

1. **Quiesce.** Close all Cowork sessions and Obsidian editor tabs. The rebuild
   is non-destructive but writes during it produce non-deterministic indexing order.

2. **Snapshot.** `tar czf 99 Workspace/_smart_env_pre_rebuild_$(date -u +%Y-%m-%dT%H%M).tar.gz .smart-env/`
   in the vault root. Keep one snapshot per rebuild for at least 30 days.

3. **Open Obsidian → Smart Connections sidebar → Settings → Smart Environment.**
   Click "Rebuild index". Wait for completion (proportional to vault source count).

4. **Run M11 smoke-test.** `python3 90 System/_smoke_test_retrieval.py`. Must pass.

5. **Run M2 eval.** Score the questions in `_eval_retrieval.md`. Document
   the run at `99 Workspace/_eval_<YYYY-MM-DD>.md`. ≥80% on all applicable dimensions.

6. **Update this file.** Bump `Index timestamp at pin` to the new
   `.smart-env/` mtime. Update `Plugin version` if changed. Bump `last_updated`.

7. **Log.** Append to `99 Workspace/_auto_writes.md` with verb `note` and
   reason "rebuilt Smart Connections index per retrieval contract".

## Cross-references

- Smart Connections plugin audit + license: `90 System/_plugin_security.md`
- Cascade documentation: `CLAUDE.md` (five-step retrieval cascade) + `90 System/_operating_guide.md` P-3
- Smoke-test (M11): `90 System/_smoke_test_retrieval.py`
- Retrieval eval (M2): `90 System/_eval_retrieval.md`
