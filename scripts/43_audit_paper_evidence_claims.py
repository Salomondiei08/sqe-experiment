"""
Audit active paper text for unsupported evidence claims.

This guard is intentionally narrow. It does not judge scientific quality. It
only blocks positive Pass@1, task-success, and human-validation claims while
the corresponding evidence gates remain missing in SUBMISSION_READINESS.json.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


FORBIDDEN_WHEN_MISSING = [
    {
        "evidence_gate": "pass1_or_task_success",
        "pattern": (
            r"\b(?:SQE|Selective-QE|our method|the method)\s+"
            r"(?:improves|improved|increases|raises|achieves|delivers)\s+"
            r"(?:downstream\s+)?(?:Pass@1|task[- ]success)"
        ),
    },
    {
        "evidence_gate": "pass1_or_task_success",
        "pattern": r"\bPass@1\s+(?:improves|improved|increases|results|score|scores|gain|gains)\b",
    },
    {
        "evidence_gate": "pass1_or_task_success",
        "pattern": r"\btask[- ]success\s+(?:improves|improved|increases|results|score|scores|gain|gains)\b",
    },
    {
        "evidence_gate": "human_audit_labels",
        "pattern": (
            r"\b(?:human[- ]audited|human reviewers?|reviewers?)\s+"
            r"(?:validate|validated|confirm|confirmed|show|showed|demonstrate|demonstrated)\b"
        ),
    },
    {
        "evidence_gate": "strong_submission",
        "pattern": r"\b(?:strong[- ]submission[- ]ready|ready for (?:top[- ]tier|top[- ]conference))\b",
    },
]

REQUIRED_LIMITATION_PHRASES = [
    "Downstream Pass@1 evaluation and human-audited query labels remain",
    "Pass@1 has not yet been measured",
    "A stronger paper requires human-audited query labels",
]


def read_json(path):
    with open(path) as f:
        return json.load(f)


def readiness_status(readiness, name):
    for check in readiness.get("checks", []):
        if check.get("name") == name:
            return check.get("status")
    return None


def gate_missing(gate, readiness):
    if gate == "pass1_or_task_success":
        return readiness_status(readiness, "Downstream Pass@1 or task-success evaluation") != "pass"
    if gate == "human_audit_labels":
        return readiness_status(readiness, "Human-audited query quality labels") != "pass"
    if gate == "strong_submission":
        return readiness.get("strong_submission_ready") is not True
    return True


def line_number(text, start):
    return text.count("\n", 0, start) + 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--paper", default="paper/main.tex")
    parser.add_argument("--readiness", default="SUBMISSION_READINESS.json")
    parser.add_argument("--output", default="PAPER_EVIDENCE_CLAIM_AUDIT.json")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    paper_path = root / args.paper
    readiness_path = root / args.readiness
    output_path = root / args.output

    failures = []
    warnings = []
    matches = []
    missing_required_limitations = []

    if not paper_path.exists():
        failures.append(f"missing paper text: {paper_path}")
        paper_text = ""
    else:
        paper_text = paper_path.read_text(errors="replace")

    if not readiness_path.exists():
        failures.append(f"missing readiness file: {readiness_path}")
        readiness = {}
    else:
        readiness = read_json(readiness_path)

    for item in FORBIDDEN_WHEN_MISSING:
        if not gate_missing(item["evidence_gate"], readiness):
            continue
        for match in re.finditer(item["pattern"], paper_text, flags=re.IGNORECASE):
            matches.append(
                {
                    "evidence_gate": item["evidence_gate"],
                    "pattern": item["pattern"],
                    "line": line_number(paper_text, match.start()),
                    "text": match.group(0),
                }
            )

    for phrase in REQUIRED_LIMITATION_PHRASES:
        if phrase not in paper_text:
            missing_required_limitations.append(phrase)

    if matches:
        failures.append("active paper contains unsupported positive evidence claims")
    if missing_required_limitations:
        failures.append("active paper is missing required evidence-limitation phrases")

    report = {
        "artifact_type": "paper_evidence_claim_audit",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "paper": str(paper_path),
        "readiness": str(readiness_path),
        "strong_submission_ready": readiness.get("strong_submission_ready"),
        "blocking_count": readiness.get("blocking_count"),
        "clean": not failures,
        "matches": matches,
        "required_limitation_phrases": REQUIRED_LIMITATION_PHRASES,
        "missing_required_limitations": missing_required_limitations,
        "warnings": warnings,
        "failures": failures,
    }
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()
