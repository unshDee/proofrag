"""Apply the documented project audit to the generated RFC candidates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .audit_goldenset import _record_sha256, _review_decision
from .rfc_corpus import load_chunks

HERE = Path(__file__).resolve().parent
GENERATED = HERE / "goldenset.generated.jsonl"
OUTPUT = HERE / "goldenset.jsonl"
REVIEW = HERE / "review.json"
EXPECTED_GENERATED_SHA256 = "cad443de0cd98135b688e2b8b5febc8ae113c0d60c26d338ebd973809aa4640b"

EDITS: dict[str, dict] = {
    "q004": {
        "question": (
            "Does the caching specification prohibit a cache from storing a response that "
            "has neither a cache validator nor an explicit expiration time?"
        ),
        "gold_answer": (
            "No. In normal operation, some caches will not store such a response because it "
            "is usually not useful to store, but caches are not prohibited from storing it."
        ),
    },
    "q006": {
        "question": (
            "When do the listed requirement keywords carry their BCP 14 meanings, and which "
            "keywords does the passage list?"
        ),
        "gold_answer": (
            "They carry the BCP 14 meanings only when written in all capitals. The listed "
            "keywords are MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, "
            "RECOMMENDED, NOT RECOMMENDED, MAY, and OPTIONAL."
        ),
    },
    "q007": {
        "question": (
            "For an HTTP/2 POST that carries request headers and content, what frame sequence "
            "and END flags does RFC 9113 specify?"
        ),
        "gold_answer": (
            "It uses one HEADERS frame, zero or more CONTINUATION frames for the request "
            "headers, and one or more DATA frames. The last CONTINUATION (or HEADERS) frame "
            "has END_HEADERS set, and the final DATA frame has END_STREAM set."
        ),
        "chunk_ids": ["rfc9113.txt::8.8.3::0"],
    },
    "q009": {
        "question": (
            "How can undefined HTTP/3 protocol elements waste peer resources, and which uses "
            "of ignorable elements does RFC 9114 identify as legitimate?"
        ),
        "gold_answer": (
            "A sender can force extra processing with multiple undefined SETTINGS parameters, "
            "unknown frame types, or unknown stream types. Legitimate uses include optional-"
            "to-understand extensions and padding that increases resistance to traffic analysis."
        ),
    },
    "q013": {
        "question": (
            "When an HTTP upgrade token does not preserve HTTP semantics and the method is "
            "otherwise irrelevant, what request form should future specifications require, "
            "and why?"
        ),
        "gold_answer": (
            "They should restrict use to GET requests with no content. This is consistent with "
            "other upgrade tokens and simplifies server implementation."
        ),
        "chunk_ids": ["rfc9931.txt::7.1::1"],
    },
    "q014": {
        "question": (
            "What must a proxy server do when it rejects an HTTP/1.1 CONNECT request from a "
            "potentially vulnerable client?"
        ),
        "gold_answer": (
            "It must close the underlying connection without processing further requests on "
            "that connection, whether or not the CONNECT request included a 'close' "
            "connection option."
        ),
    },
    "q015": {
        "question": (
            "If an origin server's ETag does not satisfy strong-validator characteristics, "
            "how must it mark the tag, and how must a cache use stored ETags for validation?"
        ),
        "gold_answer": (
            "The origin server must mark the ETag as weak by prefixing its opaque value with "
            "the case-sensitive 'W/'. When validating, the cache must send relevant stored "
            "entity tags using If-Match, If-None-Match, or If-Range."
        ),
        "chunk_ids": ["rfc9110.txt::8.8.3::3", "rfc9111.txt::4.3.1::3"],
    },
    "q016": {
        "question": (
            "For an HTTP/1.1 CONNECT tunnel requested on behalf of an untrusted TCP client, "
            "what request-target must be sent and what must the proxy client do before or "
            "while forwarding payload data?"
        ),
        "gold_answer": (
            "The request-target must be authority-form containing only the tunnel host and "
            "port, separated by a colon. The proxy client must either wait for a successful "
            "2xx response before forwarding TCP payload data or send 'Connection: close'."
        ),
        "chunk_ids": ["rfc9112.txt::3.2.3::0", "rfc9931.txt::8::0"],
    },
    "q017": {
        "question": (
            "For HTTPS connections, how do HTTP/2 and HTTP/3 identify themselves through ALPN, "
            "and what must each side send immediately after negotiation or establishment?"
        ),
        "gold_answer": (
            "HTTP/2 over TLS uses the 'h2' identifier; after TLS negotiation, client and server "
            "must each send the HTTP/2 connection preface. HTTP/3 selects 'h3' during the TLS "
            "handshake used to establish QUIC; after establishment, each endpoint must send a "
            "SETTINGS frame as the initial frame of its HTTP control stream."
        ),
        "chunk_ids": ["rfc9113.txt::3.2::0", "rfc9114.txt::3.2::1"],
    },
    "q018": {
        "question": (
            "Why does HTTP/3 replace HPACK with QPACK, and how does a QPACK encoder tell the "
            "decoder that the dynamic table capacity changed?"
        ),
        "gold_answer": (
            "HPACK depends on in-order compressed field sections, which QUIC does not guarantee, "
            "so HTTP/3 uses QPACK with separate unidirectional streams for table state. A QPACK "
            "encoder signals a new capacity with an instruction beginning with the '001' "
            "three-bit pattern followed by the capacity as an integer with a five-bit prefix."
        ),
    },
    "q019": {
        "question": (
            "How many worker threads per CPU core should an HTTP server allocate by default?"
        ),
        "gold_answer": "I don't have enough information in the provided context to answer that.",
        "chunk_ids": [],
    },
    "q020": {
        "question": (
            "How much disk space per user does HTTP Caching require a shared cache to reserve?"
        ),
        "gold_answer": "I don't have enough information in the provided context to answer that.",
        "chunk_ids": [],
    },
}

NOTES = {
    "q000": "Accepted after checking the zero-length byte-range rule against RFC 9110.",
    "q001": "Accepted after checking gateway roles and accelerator caching against RFC 9110.",
    "q002": "Accepted as a simple lexical-control definition from RFC 9110.",
    "q003": "Accepted after checking independent cache-validation request synthesis in RFC 9111.",
    "q004": "Edited to preserve RFC 9111's distinction between common behavior and prohibition.",
    "q005": "Accepted after checking chunked trailer purpose against RFC 9112.",
    "q006": "Edited to include the BCP 14 uppercase condition omitted by the candidate answer.",
    "q007": "Replaced the unsupported binary-request advice with the bound HTTP/2 frame sequence.",
    "q008": "Accepted after checking retry restrictions around GOAWAY against RFC 9113.",
    "q009": "Edited to remove an invented mitigation and retain only supported abuse examples.",
    "q010": "Accepted after checking the stated HTTP/3 and HTTP/2-with-TLS comparison.",
    "q011": "Accepted after checking QPACK and HPACK static-table index origins.",
    "q012": "Accepted after checking the non-negative QPACK Base requirement.",
    "q013": "Replaced the vague overview with specific future upgrade-token method guidance.",
    "q014": "Edited to include the no-further-processing and close-option qualifiers.",
    "q015": "Replaced unrelated range/cache passages with a two-RFC ETag validation question.",
    "q016": "Replaced a speculative link with CONNECT authority-form and payload-safety requirements.",
    "q017": "Replaced unrelated version facts with an ALPN and post-establishment comparison.",
    "q018": "Edited so both the HTTP/3 rationale and QPACK capacity instruction are necessary.",
    "q019": "Replaced an answerable cache-header question; corpus-wide worker-sizing searches were empty.",
    "q020": "Replaced an answerable GOAWAY question; corpus-wide cache-storage sizing searches were empty.",
}

ABSENCE_SEARCHES = {
    "q019": ["worker threads", "CPU core", "threads per CPU"],
    "q020": ["disk space per user", "megabytes per user", "storage quota", "cache size"],
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _bind(record: dict, chunk_ids: list[str], by_id: dict[str, dict]) -> None:
    chunks = [by_id[chunk_id] for chunk_id in chunk_ids]
    record["gold_contexts"] = [chunk["text"] for chunk in chunks]
    record["sources"] = [chunk["source"] for chunk in chunks]
    record["context_metadata"] = [
        {
            "source": chunk["source"],
            "chunk_id": chunk["chunk_id"],
            "rfc": chunk["rfc"],
            "section_number": chunk["section_number"],
            "section_title": chunk["section_title"],
            "char_count": chunk["char_count"],
        }
        for chunk in chunks
    ]


def main() -> None:
    generated_bytes = GENERATED.read_bytes()
    if _sha256(generated_bytes) != EXPECTED_GENERATED_SHA256:
        raise SystemExit("generated golden-set hash changed; refusing to apply stale review")
    generated = _read_jsonl(GENERATED)
    final = [dict(record) for record in generated]
    chunks = load_chunks()
    by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}

    for record in final:
        edit = EDITS.get(str(record["id"]))
        if edit is None:
            continue
        record["question"] = edit["question"]
        record["gold_answer"] = edit["gold_answer"]
        if "chunk_ids" in edit:
            _bind(record, edit["chunk_ids"], by_id)

    final_payload = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in final)
    final_bytes = final_payload.encode()
    cases = {}
    for candidate, record in zip(generated, final, strict=True):
        record_id = str(record["id"])
        decision = _review_decision(candidate, record)
        item = {
            "approved": True,
            "decision": decision,
            "generated_record_sha256": _record_sha256(candidate),
            "final_record_sha256": _record_sha256(record),
            "question_natural": True,
            "notes": NOTES[record_id],
        }
        if record["difficulty"] == "unanswerable":
            item["full_corpus_absence_confirmed"] = True
            item["absence_searches"] = ABSENCE_SEARCHES[record_id]
        else:
            item["answer_supported"] = True
            if record["difficulty"] == "multi_doc":
                item["requires_all_contexts"] = True
        cases[record_id] = item

    review = {
        "schema_version": 2,
        "generated_goldenset_sha256": EXPECTED_GENERATED_SHA256,
        "goldenset_sha256": _sha256(final_bytes),
        "reviewer": "project audit",
        "reviewed_at": "2026-08-10",
        "validation_scope": (
            "Project-authored semantic audit against the pinned RFC corpus; not independent "
            "human validation."
        ),
        "cases": cases,
    }
    OUTPUT.write_bytes(final_bytes)
    REVIEW.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(final)} reviewed records to {OUTPUT}", flush=True)
    print(f"Final SHA-256: {_sha256(final_bytes)}", flush=True)


if __name__ == "__main__":
    main()
