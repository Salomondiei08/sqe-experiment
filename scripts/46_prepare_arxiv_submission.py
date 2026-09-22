"""Create a minimal, self-contained arXiv source archive from the active paper."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / "paper"


def referenced_assets(tex: str, command: str) -> list[str]:
    """Return unique paths referenced by a one-argument LaTeX command."""
    pattern = rf"\\{command}(?:\[[^\]]*\])?\{{([^}}]+)\}}"
    return sorted(set(re.findall(pattern, tex)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default="/tmp/sqe_arxiv_submission")
    parser.add_argument("--skip-compile", action="store_true")
    args = parser.parse_args()

    output = Path(args.output_dir).resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    tex = (PAPER / "main.tex").read_text()
    required = ["main.tex", "references.bib"]
    required.extend(f"{path}.tex" for path in referenced_assets(tex, "input"))
    required.extend(referenced_assets(tex, "includegraphics"))

    for relative in required:
        source = PAPER / relative
        if not source.is_file():
            raise FileNotFoundError(f"Missing active paper asset: {source}")
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    if not args.skip_compile:
        subprocess.run(
            ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "main.tex"],
            cwd=output,
            check=True,
        )

    archive = output.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob("*")):
            if path.is_file() and path.suffix not in {".aux", ".bbl", ".blg", ".fdb_latexmk", ".fls", ".log", ".out", ".pdf"}:
                bundle.write(path, path.relative_to(output))

    print(f"arXiv source directory: {output}")
    print(f"arXiv upload archive: {archive}")


if __name__ == "__main__":
    main()
