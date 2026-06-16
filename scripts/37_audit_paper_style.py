"""
Audit paper formatting and style constraints that are easy to regress.

This is a deterministic guard, not an AI detector. It checks the concrete
manuscript issues that matter for this project: figure/table captions, labels,
text references, excessive manual bolding, dash/curly-quote usage, and a small
list of hype or vague wording patterns that should not appear in the active
paper.
"""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


HYPE_OR_VAGUE_PHRASES = [
    "groundbreaking",
    "revolutionary",
    "game-changing",
    "state-of-the-art",
    "cutting-edge",
    "significant improvement",
    "robust",
    "in this work",
    "seamless",
    "delve",
    "intricate",
    "realm",
    "tapestry",
    "landscape",
    "unlock",
    "unleash",
    "pivotal",
    "underscore",
    "utilize",
    "leverage",
    "moreover",
    "furthermore",
    "notably",
    "it is worth noting",
    "comprehensive",
    "extense",
    "extensive",
    "extensively",
    "novel",
]

FORBIDDEN_UNICODE_MARKS = {
    "—": "em dash",
    "–": "en dash",
    "‑": "nonbreaking hyphen",
    "“": "left curly quote",
    "”": "right curly quote",
    "‘": "left curly apostrophe",
    "’": "right curly apostrophe",
}

REQUIRED_LAYOUT_CONTROLS = [
    r"\captionsetup{font=small,labelfont=bf,skip=6pt}",
    r"\captionsetup[table]{position=top,aboveskip=7pt,belowskip=9pt}",
    r"\captionsetup[figure]{position=bottom,aboveskip=7pt,belowskip=9pt}",
    r"\setlength{\textfloatsep}{20pt plus 3pt minus 2pt}",
    r"\setlength{\floatsep}{18pt plus 3pt minus 2pt}",
    r"\setlength{\intextsep}{18pt plus 3pt minus 2pt}",
    r"\setlength{\tabcolsep}{5pt}",
    r"\renewcommand{\arraystretch}{1.08}",
    r"\emergencystretch=1em",
]


def find_envs(text, env_name):
    pattern = re.compile(
        rf"\\begin\{{{env_name}\}}(?P<body>.*?)\\end\{{{env_name}\}}",
        re.DOTALL,
    )
    return [match.group("body") for match in pattern.finditer(text)]


def labels_in_envs(envs):
    rows = []
    for idx, body in enumerate(envs, start=1):
        labels = re.findall(r"\\label\{([^}]+)\}", body)
        captions = re.findall(r"\\caption\{([^}]*)\}", body, flags=re.DOTALL)
        descriptions = re.findall(r"\\Description(?:\[[^\]]*\])?\{([^}]*)\}", body, flags=re.DOTALL)
        rows.append(
            {
                "index": idx,
                "labels": labels,
                "captions": [" ".join(caption.split()) for caption in captions],
                "descriptions": [
                    " ".join(description.split()) for description in descriptions
                ],
                "has_caption": bool(captions and captions[0].strip()),
                "has_description": bool(descriptions and descriptions[0].strip()),
                "has_label": bool(labels),
                "reference_counts": {},
            }
        )
    return rows


def main(args):
    root = Path(args.root).resolve()
    tex_path = root / "paper" / "main.tex"
    out_path = root / args.output

    problems = []
    warnings = []
    if not tex_path.exists():
        problems.append(f"missing paper source: {tex_path}")
        text = ""
    else:
        text = tex_path.read_text(errors="replace")

    figure_rows = labels_in_envs(find_envs(text, "figure"))
    table_rows = labels_in_envs(find_envs(text, "table"))

    for kind, rows in [("figure", figure_rows), ("table", table_rows)]:
        for row in rows:
            if not row["has_caption"]:
                problems.append(f"{kind} {row['index']} is missing a nonempty caption")
            if kind == "figure" and not row["has_description"]:
                problems.append(f"{kind} {row['index']} is missing a nonempty Description")
            if not row["has_label"]:
                problems.append(f"{kind} {row['index']} is missing a label")
            for label in row["labels"]:
                ref_count = len(re.findall(rf"\\(?:ref|autoref)\{{{re.escape(label)}\}}", text))
                label_count = len(re.findall(rf"\\label\{{{re.escape(label)}\}}", text))
                row["reference_counts"][label] = ref_count
                if ref_count <= 0:
                    problems.append(f"{kind} label {label} is not referenced in text")
                if label_count != 1:
                    problems.append(f"label {label} appears {label_count} times")

    forbidden_unicode_counts = {}
    for mark, name in FORBIDDEN_UNICODE_MARKS.items():
        count = text.count(mark)
        if count:
            forbidden_unicode_counts[name] = count
    if forbidden_unicode_counts:
        problems.append(f"paper contains forbidden unicode punctuation: {forbidden_unicode_counts}")

    manual_bold_count = len(re.findall(r"\\(?:textbf|bfseries)\b", text))
    if manual_bold_count > 2:
        warnings.append(
            "manual bold command count is high; use bold only for labels or captions"
        )
    if r"\sloppy" in text:
        problems.append("global \\sloppy is not allowed in the paper preamble")

    lower_text = text.lower()
    phrase_hits = []
    for phrase in HYPE_OR_VAGUE_PHRASES:
        count = lower_text.count(phrase)
        if count:
            phrase_hits.append({"phrase": phrase, "count": count})
    if phrase_hits:
        problems.append(f"hype or vague wording present: {phrase_hits}")

    unresolved_markers = re.findall(r"(?:FIXME|XXX|PLACEHOLDER)", text)
    if unresolved_markers:
        problems.append(f"unresolved markers present: {sorted(set(unresolved_markers))}")

    missing_layout_controls = [
        control for control in REQUIRED_LAYOUT_CONTROLS if control not in text
    ]
    if missing_layout_controls:
        problems.append(f"missing layout controls: {missing_layout_controls}")

    # GitHub and Hugging Face URLs are intentionally unresolved until release.
    allowed_todos = [
        "TODO: add GitHub URL",
        "TODO: add Hugging Face dataset URL",
    ]
    todo_hits = re.findall(r"TODO:[^\n}]+", text)
    unexpected_todos = sorted(set(todo_hits) - set(allowed_todos))
    if unexpected_todos:
        problems.append(f"unexpected TODO markers present: {unexpected_todos}")

    report = {
        "paper": str(tex_path),
        "figures": figure_rows,
        "tables": table_rows,
        "n_figures": len(figure_rows),
        "n_tables": len(table_rows),
        "manual_bold_count": manual_bold_count,
        "em_dash_count": text.count("—"),
        "forbidden_unicode_punctuation_counts": forbidden_unicode_counts,
        "guarded_phrases": HYPE_OR_VAGUE_PHRASES,
        "hype_or_vague_phrase_hits": phrase_hits,
        "required_layout_controls": REQUIRED_LAYOUT_CONTROLS,
        "missing_layout_controls": missing_layout_controls,
        "allowed_todos": allowed_todos,
        "unexpected_todos": unexpected_todos,
        "warnings": warnings,
        "failures": problems,
        "clean": not problems,
    }
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default="PAPER_STYLE_AUDIT.json")
    raise SystemExit(main(parser.parse_args()))
