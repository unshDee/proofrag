# Security

Please report a suspected proofrag vulnerability through
[GitHub private vulnerability reporting](https://github.com/unshDee/proofrag/security/advisories/new).
Do not include API keys, private prompts, customer data, or signed URLs.

## Optional dependency advisories

Reviewed October 4, 2026 after refreshing the lockfile. The core package and Jev
backend have no mandatory third-party runtime dependencies. Installing extras
adds the security surface of the selected libraries.

The full development and all-extras environment audit found these two distinct
upstream advisories. The advisory feed lists no patched versions for either one.
They remain known upstream findings rather than fixed vulnerabilities.

| Package | Advisory | Reachability in proofrag |
| --- | --- | --- |
| Ragas 0.4.3 | [CVE-2026-6587](https://github.com/advisories/GHSA-95ww-475f-pr4f) concerns URL and local-file access in a multimodal faithfulness collection | proofrag selects text-only Faithfulness, FactualCorrectness, and optional ResponseRelevancy. It does not select the affected multimodal collection or convert context text into image inputs |
| DiskCache 5.6.3 through Ragas | [CVE-2025-69872](https://github.com/advisories/GHSA-w8v5-vhqr-4h9v) concerns pickle deserialization from an attacker-writable cache directory | proofrag does not construct DiskCacheBackend. Its Ragas LLM and embedding wrappers use the default cache=None |

This path review describes the current adapters. It does not establish that every
feature in Ragas is safe. Applications that directly enable Ragas multimodal
metrics or disk caching must assess those features separately. Recheck advisories
and package releases before changing the adapters.

## Evaluation boundaries

Treat corpora, golden sets, predictions, and model outputs as untrusted data.
Text is encoded as data in built-in prompts. This reduces prompt confusion but
does not guarantee protection from model-level prompt injection. Scores and
confidence are model judgments, not verified facts.

HTTP adapters require HTTPS for remote servers, limit response size, and block
cross-origin redirects. Python callable adapters run application code in the
current process. Only load callables from code you trust.
