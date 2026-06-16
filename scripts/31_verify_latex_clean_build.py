"""
Compile the SQE paper and fail if the LaTeX build emits warnings.

This is a build-quality audit only. It does not read, write, or generate
experiment metrics.
"""

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


WARNING_PATTERNS = [
    r"\bwarning:",
    r"Overfull \\hbox",
    r"Underfull \\hbox",
    r"LaTeX Warning:",
    r"Package .* Warning:",
    r"undefined references",
    r"Rerun to get",
]


def get_pdf_pages(pdf_path):
    pdfinfo = shutil.which("pdfinfo")
    if not pdfinfo or not pdf_path.exists():
        return None
    proc = subprocess.run(
        [pdfinfo, str(pdf_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def main(args):
    root = Path(args.root).resolve()
    paper_dir = (root / args.paper_dir).resolve()
    tex_path = paper_dir / args.tex
    output_path = root / args.output
    tectonic = args.tectonic or shutil.which("tectonic") or shutil.which("tectonic-musl")

    report = {
        "root": str(root),
        "paper_dir": str(paper_dir),
        "tex": str(tex_path),
        "tectonic": tectonic,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "returncode": None,
        "warning_patterns": WARNING_PATTERNS,
        "warnings": [],
        "failures": [],
    }

    if not tex_path.exists():
        report["failures"].append(f"missing TeX source: {tex_path}")
    if not tectonic:
        report["failures"].append("tectonic executable not found")

    if not report["failures"]:
        proc = subprocess.run(
            [tectonic, tex_path.name],
            cwd=paper_dir,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        report["returncode"] = proc.returncode
        log = proc.stdout
        report["log_tail"] = log[-6000:]
        if proc.returncode != 0:
            report["failures"].append(f"tectonic exited with {proc.returncode}")

        warning_hits = []
        for pattern in WARNING_PATTERNS:
            if re.search(pattern, log, flags=re.IGNORECASE):
                warning_hits.append(pattern)
        report["warnings"] = warning_hits
        if warning_hits:
            report["failures"].append(f"LaTeX build warnings matched: {warning_hits}")

        pdf_path = tex_path.with_suffix(".pdf")
        report["pdf"] = str(pdf_path)
        report["pdf_bytes"] = pdf_path.stat().st_size if pdf_path.exists() else 0
        report["pdf_pages"] = get_pdf_pages(pdf_path)
        if not pdf_path.exists() or pdf_path.stat().st_size < 10000:
            report["failures"].append(f"missing or unexpectedly small PDF: {pdf_path}")

    report["clean_build"] = not report["failures"]
    output_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["clean_build"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="/home/nlp-07/sqe_experiment")
    parser.add_argument("--paper_dir", default="paper")
    parser.add_argument("--tex", default="main.tex")
    parser.add_argument("--tectonic", default="/home/nlp-07/.local/bin/tectonic-musl")
    parser.add_argument("--output", default="LATEX_BUILD_AUDIT.json")
    raise SystemExit(main(parser.parse_args()))
