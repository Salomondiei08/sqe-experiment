"""Build a two-column conference-layout preview from the active paper.

This is not a venue template and does not claim ACL, NeurIPS, or ICLR
compliance. It gives a paper-like two-column layout for readability checks while
keeping the active verified manuscript and experiment evidence unchanged.
"""

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"


def make_preview_tex(source):
    tex = source
    tex = tex.replace(
        r"\documentclass[10pt]{article}",
        r"\documentclass[10pt,twocolumn]{article}",
    )
    tex = tex.replace(
        r"\usepackage[letterpaper,margin=1in]{geometry}",
        r"\usepackage[letterpaper,margin=0.75in,columnsep=0.25in]{geometry}",
    )
    tex = tex.replace(
        r"\includegraphics[width=0.92\linewidth]",
        r"\includegraphics[width=0.86\textwidth]",
    )
    tex = tex.replace(
        r"\includegraphics[width=0.95\linewidth]",
        r"\includegraphics[width=0.86\textwidth]",
    )
    tex = tex.replace(r"\begin{figure}[!tbp]", r"\begin{figure*}[!tbp]")
    tex = tex.replace(r"\end{figure}", r"\end{figure*}")
    tex = tex.replace(r"\begin{table}[!tbp]", r"\begin{table*}[!tbp]")
    tex = tex.replace(r"\end{table}", r"\end{table*}")
    tex = tex.replace("\n\\small\n\\input", "\n\\scriptsize\n\\input")
    tex = tex.replace(
        r"\title{Selective Query-Side Expansion for Long-Horizon Agent Memory Retrieval}",
        r"\title{\vspace{-1.5em}Selective Query-Side Expansion for Long-Horizon Agent Memory Retrieval}",
    )
    return tex


def count_pdf_pages(path):
    try:
        proc = subprocess.run(
            ["pdfinfo", str(path)],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception:
        return None
    match = re.search(r"^Pages:\s+(\d+)$", proc.stdout, re.MULTILINE)
    return int(match.group(1)) if match else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tectonic", default=str(Path.home() / ".local/bin/tectonic-musl"))
    parser.add_argument("--output", default="paper/main_conference_preview.tex")
    parser.add_argument("--audit", default="CONFERENCE_PREVIEW_AUDIT.json")
    args = parser.parse_args()

    source_path = PAPER / "main.tex"
    output_path = ROOT / args.output
    audit_path = ROOT / args.audit
    output_path.write_text(make_preview_tex(source_path.read_text()))

    proc = subprocess.run(
        [args.tectonic, output_path.name],
        cwd=output_path.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    pdf_path = output_path.with_suffix(".pdf")
    warnings = [
        line
        for line in proc.stdout.splitlines()
        if "warning:" in line.lower()
        or "overfull \\hbox" in line
        or "underfull \\hbox" in line
        or "underfull \\vbox" in line
    ]
    failures = []
    if proc.returncode:
        failures.append(f"tectonic exited with {proc.returncode}")
    if any("Overfull \\hbox" in line for line in warnings):
        failures.append("conference preview has overfull hbox warnings")

    report = {
        "artifact_type": "conference_layout_preview",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_tex": str(source_path),
        "preview_tex": str(output_path),
        "preview_pdf": str(pdf_path),
        "tectonic": args.tectonic,
        "returncode": proc.returncode,
        "warnings": warnings,
        "failures": failures,
        "clean_for_preview": proc.returncode == 0 and not failures,
        "is_official_venue_template": False,
        "is_experiment_evidence": False,
        "pdf_pages": count_pdf_pages(pdf_path) if pdf_path.exists() else None,
        "pdf_bytes": pdf_path.stat().st_size if pdf_path.exists() else None,
        "note": (
            "This preview is for two-column layout review only. Use the target "
            "conference's official style files before submission."
        ),
    }
    audit_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
