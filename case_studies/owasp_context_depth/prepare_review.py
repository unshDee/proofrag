"""Materialize the documented project audit of the generated OWASP candidates."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from proofrag.corpus import load_corpus

from .download_corpus import COMMIT
from .rag import CHUNK_CHARS

HERE = Path(__file__).resolve().parent
GENERATED = HERE / "goldenset.generated.jsonl"
REVIEWED = HERE / "goldenset.reviewed.jsonl"
REVIEW = HERE / "review.json"
CORPUS = HERE / "corpus"
EXPECTED_GENERATED_SHA256 = "c5607d88e82289f1d5c9758b0e40335ebdb4fcdc356b4eb990ec305089e0c5be"
REFUSAL = "I don't have enough information in the provided context to answer that."

EDITS: dict[str, dict[str, Any]] = {
    "q005": {
        "question": (
            "Which three strong, slow password-hashing algorithms does the passage give "
            "as examples?"
        ),
        "gold_answer": "It gives Argon2id, bcrypt, and PBKDF2 as examples.",
    },
    "q006": {
        "question": (
            "What example of sensitive data can a session object contain, and how must "
            "the session-management repository be protected in that case?"
        ),
        "gold_answer": (
            "A session object can contain credit card numbers. If session objects or "
            "properties contain such sensitive information, the repository must be "
            "encrypted and protected."
        ),
    },
    "q013": {
        "question": (
            "Which Rust crate and crate version does OWASP recommend for implementing "
            "Argon2id password hashing?"
        ),
        "gold_answer": REFUSAL,
        "difficulty": "unanswerable",
        "chunk_ids": [],
    },
    "q014": {
        "question": (
            "What common idle-timeout ranges does the passage give for high-value and "
            "low-risk applications?"
        ),
        "gold_answer": (
            "It gives 2–5 minutes for high-value applications and 15–30 minutes for "
            "low-risk applications."
        ),
    },
    "q017": {
        "question": (
            "For a sensitive account change, what credential check should an application "
            "require, and why would asking for both a password and a PIN still not count "
            "as MFA?"
        ),
        "gold_answer": (
            "Before changing sensitive account information, the application should require "
            "the account's current credentials to mitigate CSRF and session hijacking. A "
            "password and PIN are both knowledge factors, so requiring both is only two "
            "instances of the same factor, does not constitute MFA, and offers minimal "
            "additional security. MFA factors should be independent."
        ),
        "chunk_ids": [
            "Authentication_Cheat_Sheet.md::22",
            "Multifactor_Authentication_Cheat_Sheet.md::3",
        ],
    },
    "q018": {
        "question": (
            "Which lifecycle controls should password-reset tokens have, and how must a "
            "repository that temporarily stores session IDs be protected?"
        ),
        "gold_answer": (
            "Reset tokens should be generated with a cryptographically secure random "
            "number generator, be long enough to resist brute force, be linked to one "
            "user, be invalidated after use, and be stored securely. A session-ID "
            "repository must protect the IDs against accidental disclosure or unauthorized "
            "access through both local and remote attacks."
        ),
        "chunk_ids": [
            "Forgot_Password_Cheat_Sheet.md::12",
            "Session_Management_Cheat_Sheet.md::29",
        ],
    },
    "q019": {
        "question": (
            "How do client certificates and password peppering protect different attack surfaces?"
        ),
        "gold_answer": (
            "A client certificate is stored on the user's device and automatically "
            "presented alongside the password during authentication. Peppering adds a "
            "layer beyond salting so an attacker who obtains only the password database "
            "cannot crack its hashes. The first strengthens authentication at the client; "
            "the second protects stored password hashes after a database-only compromise."
        ),
    },
    "q020": {
        "question": (
            "How do work factors for stored passwords and entropy for session IDs make "
            "brute-force attacks harder in different ways?"
        ),
        "gold_answer": (
            "A password-hash work factor increases the computation required for every "
            "guess, reducing attacker speed or increasing cost. A session ID needs at "
            "least 64 bits of entropy so the space of possible identifiers is large enough "
            "to prevent practical brute-force guessing."
        ),
        "chunk_ids": [
            "Password_Storage_Cheat_Sheet.md::19",
            "Session_Management_Cheat_Sheet.md::15",
        ],
    },
    "q021": {
        "question": (
            "What separate threats are addressed by validating session IDs as untrusted "
            "input and by U2F's use of the website URL?"
        ),
        "gold_answer": (
            "Validating and filtering session IDs helps prevent them from becoming input "
            "to vulnerabilities such as SQL injection. U2F uses the website URL to select "
            "the stored authentication key, which protects against phishing."
        ),
    },
    "q022": {
        "question": (
            "Which commercial MFA provider does OWASP rank first for an application with "
            "10,000 users, and what monthly price does it quote?"
        ),
        "gold_answer": REFUSAL,
    },
    "q023": {
        "question": (
            "Which iOS SDK classes and minimum iOS version does OWASP require for "
            "implementing FIDO2 or passkey authentication?"
        ),
        "gold_answer": REFUSAL,
    },
}

DECISIONS = {
    "q005": "edited",
    "q006": "edited",
    "q013": "replaced",
    "q014": "edited",
    "q017": "replaced",
    "q018": "replaced",
    "q019": "edited",
    "q020": "replaced",
    "q021": "edited",
    "q022": "replaced",
    "q023": "edited",
}

NOTES = {
    "q000": "Confirmed the cookie-only exchange guidance and session-fixation rationale.",
    "q001": "Confirmed all five HTTP session-state mechanisms listed in the cited chunk.",
    "q002": "Confirmed the recipients, notification/confirmation distinction, and purposes.",
    "q003": "Confirmed the three JavaScript-accessible fingerprint attributes.",
    "q004": "Confirmed the binding between credentials, HTTP traffic, and access controls.",
    "q005": "Changed 'recommended algorithms' to examples, matching the passage's wording.",
    "q006": "Narrowed a plural claim to the credit-card example and stated its protection.",
    "q007": "Confirmed the PHP password_verify example and comparison purpose.",
    "q008": "Confirmed why distinct salts conceal equal passwords without cracking.",
    "q009": "Confirmed the hexadecimal length needed to encode 64 bits of entropy.",
    "q010": "Confirmed password strength as the stated authentication concern.",
    "q011": "Confirmed both risk-signal and fallback-mechanism implementation concerns.",
    "q012": "Confirmed the server-side timeout requirement and client-tampering rationale.",
    "q013": "Replaced an overrepresented session case with a corpus-absent Rust question.",
    "q014": "Changed 'recommended' to 'common' timeout ranges to match the passage.",
    "q015": "Confirmed all five contextual attributes in the cited passage.",
    "q016": "Confirmed the one-way-hashing rationale and direct-login consequence.",
    "q017": "Rebuilt with complete chunks; each clause requires a different source.",
    "q018": "Rebuilt around reset-token lifecycle controls and session-ID repository safety.",
    "q019": "Removed unsupported detail and retained a two-source attack-surface comparison.",
    "q020": "Replaced a speculative analogy with the documented cost-versus-entropy contrast.",
    "q021": "Removed unsupported generalization; retained SQL-injection and phishing controls.",
    "q022": "Replaced an answerable protocol comparison with absent vendor ranking and pricing.",
    "q023": "Narrowed the absent information to concrete iOS APIs and version requirements.",
}

ABSENCE_QUERIES = {
    "q013": ["rust crate", "cargo add argon2"],
    "q022": ["10,000 users", "monthly price"],
    "q023": ["minimum ios version", "authenticationservices framework"],
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bind(record: dict[str, Any], chunk_ids: list[str], chunks: dict[str, dict]) -> None:
    selected = [chunks[chunk_id] for chunk_id in chunk_ids]
    record["gold_contexts"] = [chunk["text"] for chunk in selected]
    record["sources"] = [
        f"case_studies/owasp_context_depth/corpus/{Path(chunk['source']).name}"
        for chunk in selected
    ]
    record["context_metadata"] = [
        {
            "source": f"case_studies/owasp_context_depth/corpus/{Path(chunk['source']).name}",
            "chunk_id": chunk["chunk_id"],
            "chunk_index": chunk["chunk_index"],
            "char_count": chunk["char_count"],
            "extension": chunk["extension"],
        }
        for chunk in selected
    ]


def main() -> None:
    if _sha256(GENERATED) != EXPECTED_GENERATED_SHA256:
        raise SystemExit("generated candidates changed; repeat the semantic audit")
    generated = [json.loads(line) for line in GENERATED.read_text().splitlines() if line]
    if [record["id"] for record in generated] != [f"q{i:03d}" for i in range(24)]:
        raise SystemExit("generated candidates must contain q000 through q023")
    chunks = {chunk["chunk_id"]: chunk for chunk in load_corpus(str(CORPUS), max_chars=CHUNK_CHARS)}
    reviewed = copy.deepcopy(generated)
    for record in reviewed:
        edit = EDITS.get(record["id"], {})
        for field in ("question", "gold_answer", "difficulty"):
            if field in edit:
                record[field] = edit[field]
        if "chunk_ids" in edit:
            _bind(record, edit["chunk_ids"], chunks)

    rendered = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in reviewed)
    REVIEWED.write_text(rendered, encoding="utf-8")
    cases: dict[str, dict[str, Any]] = {}
    for generated_record, record in zip(generated, reviewed, strict=True):
        record_id = record["id"]
        decision = DECISIONS.get(record_id, "accepted")
        if (record == generated_record) != (decision == "accepted"):
            raise SystemExit(f"review decision does not match changes for {record_id}")
        case: dict[str, Any] = {"decision": decision, "note": NOTES[record_id]}
        if record["difficulty"] == "unanswerable":
            case["absence_queries"] = ABSENCE_QUERIES[record_id]
        else:
            case["evidence_sources"] = list(
                dict.fromkeys(Path(source).name for source in record["sources"])
            )
        cases[record_id] = case
    review = {
        "schema_version": 1,
        "source_commit": COMMIT,
        "generated_sha256": _sha256(GENERATED),
        "reviewed_sha256": _sha256(REVIEWED),
        "reviewed_by": "project audit",
        "reviewed_at": "2026-08-10",
        "review_scope": (
            "Project-level semantic and exact-evidence audit; not independent human or "
            "domain-expert validation."
        ),
        "cases": cases,
    }
    REVIEW.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(reviewed)} reviewed cases -> {REVIEWED}", flush=True)
    print(f"Reviewed SHA-256: {_sha256(REVIEWED)}", flush=True)


if __name__ == "__main__":
    main()
