# Claude Obsidian Vault Framework

A structured knowledge base framework for Claude in Cowork, built on the Karpathy "LLM as OS" pattern.

---

## The idea

Andrej Karpathy described the LLM as an operating system: give it an index file, have it read that first to orient itself, then drill into the notes it finds. The key insight is that a single RAG lookup is the wrong unit of retrieval — a well-designed system walks a *cascade* (lexical → semantic → structured → link-expand → deep-read), stops at the first clean hit, and knows how to say "I don't have enough signal" when no step fires.

This framework operationalises that pattern into a production knowledge base co-pilot. It gives Claude 9 behavioural rules (P-rules) that govern how it reads, writes, promotes, and evaluates your vault. It layers a 5-step retrieval cascade on top of Smart Connections semantic search, adds a cross-encoder reranker for precision on long files, scores the whole system with a 33-question eval harness, and logs every write to an Ed25519-signed audit chain. The Karpathy pattern is the foundation; the framework builds the rest of the operating system on top of it.

---

## What's included

| Plugin | What it gives you |
|---|---|
| **vault-framework** | Core kernel: CLAUDE.md template, operating guide (9 P-rules), 11 rules files, 12 Bases templates, `/vault-setup` `/hot` `/promote` commands, `populate-claude-md.py`, `verify_baseline.py` |
| **vault-skills** | Active maintenance: kb-curator (KB health), plan-builder (session plans), save-conversation, autoresearch-loop |
| **vault-eval** | 33-question retrieval eval template, `smoke_test_retrieval.py`, `rerank.py` (BAAI/bge-reranker-v2-m3 cross-encoder), `eval_faithfulness.py` |
| **vault-ingestion** | `ingest.py` + 9 file handlers (pdf, docx, pptx, xlsx, text, image, html, semantic, links), `config.yaml`, ingestion contract template |
| **vault-voice** | `voice-discipline.md`, `voice-profile-template.md`, `writing-craft-template.md`, `populate-voice-profile.py` |

---

## What goes beyond Karpathy

The index-first, cascade-walk pattern is Karpathy's. These layers are not:

- **Ed25519-signed audit chain** — every write is logged to `_auto_writes.md` with a cryptographic hash chain. `_audit_chain.py verify` detects tampering. Weekly health task compares the chain against git history.
- **33-question eval harness** — 6 scoring dimensions (S/X/T/MH/CAL/F). Measures cascade performance like a test suite. Without this, you don't know if P-rules 3 actually works.
- **Calibrated refusal** — Claude says `Confidence: low — [reason]` when retrieval is thin, and `REFUSE` (with a structured response) when all five steps return dead ends. It never invents a claim to fill a vault gap.
- **Closed-loop recommendation registry** — health tasks emit structured recommendations to `_recommendations_open.jsonl`. Tiered expiry (T1/T2/T3). Claude surfaces T3 rows at session bootstrap before substantive work begins.
- **Nightly autoresearch cascade optimisation** — hill-climbs on the eval score by iterating over the cascade's editable surface (rules, thresholds, rerank parameters). Runs unattended; surfaces a diff for approval. See ARCHITECTURE.md.
- **Multilingual fall-through (M9)** — for content in a non-primary language, skip the semantic step (Smart Connections embedding space is English-optimised) and go directly to Bases queries.

---

## Quick install

**Path A — You have Obsidian and a project folder:**
```
/plugin marketplace add https://github.com/<owner>/claude-obsidian-vault
/plugin install vault-framework@claude-obsidian-vault
/vault-setup
```

**Path B — No Obsidian yet:**
```bash
git clone https://github.com/<owner>/claude-obsidian-vault
./scripts/bootstrap.sh   # installs Obsidian, prompts Smart Connections + Bases
# then follow Path A
```

**Path C — Framework already installed, new project:**
```
# Open Cowork on the new folder, then:
/vault-setup
# auto-detects framework at user scope, just scaffolds the new folder
```

Full step-by-step, troubleshooting, and verification in [INSTALL.md](INSTALL.md).

---

## Status

**Experimental / early-access.** Tested on macOS + Cowork (Claude for Desktop). Requires:
- [Smart Connections](https://github.com/brianpetro/obsidian-smart-connections) (community plugin — semantic retrieval substrate)
- Bases (Obsidian core plugin — structured queries)
- Python 3.9+ (for ingestion pipeline and eval scripts)

Linux support is tracked but not yet tested. Windows is not currently supported.

---

## License

MIT — see [LICENSE](LICENSE).
