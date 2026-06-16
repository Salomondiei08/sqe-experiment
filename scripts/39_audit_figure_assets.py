"""
Audit active paper figure assets for basic readability and renderability.

This is a deterministic visual-quality guard. It does not judge scientific
content. It checks that every figure referenced by paper/main.tex exists as a
PNG, has a matching SVG source, is large enough for print review, is not mostly
dark, and contains text elements in the SVG source for titles, axis labels, or
legends.
"""

import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def png_metrics(path):
    try:
        from PIL import Image, ImageStat
    except Exception as exc:
        return {"error": f"Pillow import failed: {exc}"}

    try:
        with Image.open(path) as img:
            image = img.convert("RGB")
            stat = ImageStat.Stat(image)
            mean_luminance = sum(stat.mean) / 3.0
            sample = image.resize(
                (max(1, image.width // 8), max(1, image.height // 8))
            )
            n_pixels = 0
            dark_pixels = 0
            nonwhite_pixels = 0
            pixel_iter = (
                sample.get_flattened_data()
                if hasattr(sample, "get_flattened_data")
                else sample.getdata()
            )
            for red, green, blue in pixel_iter:
                n_pixels += 1
                luminance = 0.2126 * red + 0.7152 * green + 0.0722 * blue
                if luminance < 80:
                    dark_pixels += 1
                if min(red, green, blue) < 245:
                    nonwhite_pixels += 1
            return {
                "width": image.width,
                "height": image.height,
                "mode": image.mode,
                "mean_luminance": round(mean_luminance, 2),
                "dark_pixel_pct": round(100.0 * dark_pixels / max(1, n_pixels), 3),
                "nonwhite_pixel_pct": round(
                    100.0 * nonwhite_pixels / max(1, n_pixels), 3
                ),
            }
    except Exception as exc:
        return {"error": str(exc)}


def active_figures(tex):
    return sorted(
        set(re.findall(r"\\includegraphics\[[^\]]+\]\{figures/([^}]+)\}", tex))
    )


def audit(root):
    paper = root / "paper" / "main.tex"
    figures_dir = root / "paper" / "figures"
    failures = []
    warnings = []
    rows = []

    if not paper.exists():
        return {
            "paper": str(paper),
            "figures": [],
            "failures": [f"missing paper source: {paper}"],
            "warnings": [],
            "clean": False,
        }

    tex = paper.read_text(errors="replace")
    for figure_name in active_figures(tex):
        png_path = figures_dir / figure_name
        stem = png_path.stem
        svg_path = figures_dir / f"{stem}.svg"
        metrics = png_metrics(png_path) if png_path.exists() else {}
        svg_text = svg_path.read_text(errors="replace") if svg_path.exists() else ""
        text_element_count = len(re.findall(r"<text\b", svg_text))
        row_failures = []

        if not png_path.exists():
            row_failures.append(f"missing active figure PNG: {png_path}")
        if not svg_path.exists():
            row_failures.append(f"missing SVG source for active figure: {svg_path}")
        if metrics.get("error"):
            row_failures.append(f"{figure_name} could not be read: {metrics['error']}")
        if metrics and not metrics.get("error"):
            if metrics["width"] < 1200 or metrics["height"] < 700:
                row_failures.append(
                    f"{figure_name} is too small for review: "
                    f"{metrics['width']}x{metrics['height']}"
                )
            if metrics["mean_luminance"] < 215:
                row_failures.append(
                    f"{figure_name} is too dark: mean_luminance="
                    f"{metrics['mean_luminance']}"
                )
            if metrics["dark_pixel_pct"] > 5.0:
                row_failures.append(
                    f"{figure_name} has too many dark pixels: "
                    f"{metrics['dark_pixel_pct']}%"
                )
            if metrics["nonwhite_pixel_pct"] < 2.0:
                row_failures.append(
                    f"{figure_name} appears nearly blank: nonwhite_pixel_pct="
                    f"{metrics['nonwhite_pixel_pct']}%"
                )
        if svg_path.exists() and text_element_count < 4:
            row_failures.append(
                f"{figure_name} SVG has too few text elements for title/labels/legend"
            )

        rows.append(
            {
                "figure": figure_name,
                "png": str(png_path),
                "svg": str(svg_path),
                "png_present": png_path.exists(),
                "svg_present": svg_path.exists(),
                "text_element_count": text_element_count,
                "metrics": metrics,
                "failures": row_failures,
            }
        )
        failures.extend(row_failures)

    if not rows:
        failures.append("paper/main.tex does not reference any figures")

    return {
        "paper": str(paper),
        "n_active_figures": len(rows),
        "figures": rows,
        "warnings": warnings,
        "failures": failures,
        "clean": not failures,
    }


def main(args):
    root = Path(args.root).resolve()
    report = audit(root)
    out_path = root / args.output
    out_path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["clean"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default="FIGURE_ASSET_AUDIT.json")
    raise SystemExit(main(parser.parse_args()))
