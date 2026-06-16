"""
Build a conference-ready PowerPoint deck for the SQE project.

This script intentionally uses only the Python standard library because the
server does not have pip, python-pptx, pandoc, or LibreOffice available. It
creates a compact Office Open XML presentation with embedded PNG figures and a
separate speaker-notes markdown file.
"""

from __future__ import annotations

import json
import re
import struct
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation"
FIGURES = ROOT / "paper" / "figures"
RESULTS = ROOT / "results_500_memory_seed42"
MULTISEED = ROOT / "paper" / "tables" / "multiseed_summary.tex"
PAIRED = ROOT / "paper" / "tables" / "multiseed_paired_tests.tex"

SLIDE_W = 12192000
SLIDE_H = 6858000
EMU_PER_IN = 914400

NS_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"

COLORS = {
    "ink": "172033",
    "muted": "5B6472",
    "blue": "2E6F9E",
    "blue_light": "E8F2F8",
    "orange": "CF7F3F",
    "orange_light": "FFF3E8",
    "green": "3F8F67",
    "green_light": "EAF7F0",
    "gray": "EEF2F6",
    "line": "C9D3DE",
    "white": "FFFFFF",
    "red": "B42318",
}


def pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def read_json(path: Path):
    with path.open() as f:
        return json.load(f)


def load_seed42():
    baseline = read_json(RESULTS / "baselines_summary.json")
    rows = {r["method"]: r for r in baseline}
    rows["Selective-QE"] = read_json(RESULTS / "proposed_summary.json")
    rows["Always-Expand"] = read_json(RESULTS / "always_expand_summary.json")
    rows["Random-Gated-Expansion"] = read_json(RESULTS / "random_budget_summary.json")
    return rows


def table_rows(path: Path):
    if not path.exists():
        return []
    text = path.read_text()
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if "&" not in line or line.startswith("\\") or line.startswith("Method"):
            continue
        line = line.rstrip("\\").strip()
        cells = [re.sub(r"\\[a-zA-Z]+", "", c).strip("{} ") for c in line.split("&")]
        rows.append(cells)
    return rows


def png_size(path: Path):
    with path.open("rb") as f:
        sig = f.read(24)
    if sig[:8] != b"\x89PNG\r\n\x1a\n":
        return 1200, 800
    return struct.unpack(">II", sig[16:24])


def xml_text(text: str) -> str:
    return escape(str(text), {'"': "&quot;"})


def x(inches: float) -> int:
    return int(inches * EMU_PER_IN)


def paragraph(text: str, size=24, color="ink", bold=False, align="l"):
    weight = ' b="1"' if bold else ""
    return (
        f'<a:p><a:pPr algn="{align}"/>'
        f'<a:r><a:rPr lang="en-US" sz="{size * 100}"{weight}>'
        f'<a:solidFill><a:srgbClr val="{COLORS[color]}"/></a:solidFill>'
        f"</a:rPr><a:t>{xml_text(text)}</a:t></a:r></a:p>"
    )


def multiline_paragraphs(lines, size=24, color="ink", bold_first=False):
    return "\n".join(
        paragraph(line, size=size, color=color, bold=(bold_first and i == 0))
        for i, line in enumerate(lines)
    )


def shape(shape_id, name, left, top, width, height, fill="white", line="line", radius=False, text="", size=24, color="ink", bold=False, align="l"):
    prst = "roundRect" if radius else "rect"
    tx = ""
    if text:
        tx = (
            "<p:txBody><a:bodyPr wrap=\"square\" lIns=\"152400\" tIns=\"91440\" "
            "rIns=\"152400\" bIns=\"91440\"/><a:lstStyle/>"
            f"{paragraph(text, size=size, color=color, bold=bold, align=align)}</p:txBody>"
        )
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="{xml_text(name)}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>
    <a:prstGeom prst="{prst}"><a:avLst/></a:prstGeom>
    <a:solidFill><a:srgbClr val="{COLORS[fill]}"/></a:solidFill>
    <a:ln w="12700"><a:solidFill><a:srgbClr val="{COLORS[line]}"/></a:solidFill></a:ln>
  </p:spPr>
  {tx}
</p:sp>
"""


def text_box(shape_id, name, left, top, width, height, lines, size=24, color="ink", bold_first=False, align="l"):
    return f"""
<p:sp>
  <p:nvSpPr><p:cNvPr id="{shape_id}" name="{xml_text(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    <a:noFill/><a:ln><a:noFill/></a:ln>
  </p:spPr>
  <p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>
    {multiline_paragraphs(lines, size=size, color=color, bold_first=bold_first)}
  </p:txBody>
</p:sp>
"""


def image_pic(pic_id, name, rel_id, left, top, width, height):
    return f"""
<p:pic>
  <p:nvPicPr><p:cNvPr id="{pic_id}" name="{xml_text(name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
  <p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
  <p:spPr><a:xfrm><a:off x="{left}" y="{top}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr>
</p:pic>
"""


def line(shape_id, x1, y1, x2, y2, color="line", width=19050, arrow=False):
    arrow_xml = '<a:tailEnd type="triangle"/>' if arrow else ""
    return f"""
<p:cxnSp>
  <p:nvCxnSpPr><p:cNvPr id="{shape_id}" name="Line {shape_id}"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
  <p:spPr>
    <a:xfrm><a:off x="{min(x1, x2)}" y="{min(y1, y2)}"/><a:ext cx="{abs(x2-x1)}" cy="{abs(y2-y1)}"/></a:xfrm>
    <a:prstGeom prst="line"><a:avLst/></a:prstGeom>
    <a:ln w="{width}"><a:solidFill><a:srgbClr val="{COLORS[color]}"/></a:solidFill>{arrow_xml}</a:ln>
  </p:spPr>
</p:cxnSp>
"""


def slide_xml(shapes):
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:cSld><p:spTree>
    <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
    <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    {''.join(shapes)}
  </p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"""


def content_types(n_slides, images):
    image_overrides = "\n".join(
        f'<Override PartName="/ppt/media/{name}" ContentType="image/png"/>'
        for name in images
    )
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, n_slides + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Default Extension="png" ContentType="image/png"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  {slide_overrides}
  {image_overrides}
</Types>
"""


def root_rels():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"""


def presentation_xml(n_slides):
    slide_ids = "\n".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i}"/>' for i in range(1, n_slides + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" saveSubsetFonts="1">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{n_slides + 1}"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle/>
</p:presentation>
"""


def presentation_rels(n_slides):
    rels = [
        f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, n_slides + 1)
    ]
    rels.append(
        f'<Relationship Id="rId{n_slides + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>'
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {' '.join(rels)}
</Relationships>
"""


def slide_rels(images):
    rels = [
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
    ]
    for i, image_name in enumerate(images, start=2):
        rels.append(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/{image_name}"/>'
        )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  {' '.join(rels)}
</Relationships>
"""


def layout_xml():
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""


def master_xml():
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="{NS_A}" xmlns:r="{NS_R}" xmlns:p="{NS_P}">
  <p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>
"""


def master_rels():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>
"""


def layout_rels():
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>
"""


def theme_xml():
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="{NS_A}" name="SQE Clean">
  <a:themeElements>
    <a:clrScheme name="SQE"><a:dk1><a:srgbClr val="172033"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="5B6472"/></a:dk2><a:lt2><a:srgbClr val="EEF2F6"/></a:lt2><a:accent1><a:srgbClr val="2E6F9E"/></a:accent1><a:accent2><a:srgbClr val="CF7F3F"/></a:accent2><a:accent3><a:srgbClr val="3F8F67"/></a:accent3><a:accent4><a:srgbClr val="C9D3DE"/></a:accent4><a:accent5><a:srgbClr val="B42318"/></a:accent5><a:accent6><a:srgbClr val="667085"/></a:accent6><a:hlink><a:srgbClr val="2E6F9E"/></a:hlink><a:folHlink><a:srgbClr val="2E6F9E"/></a:folHlink></a:clrScheme>
    <a:fontScheme name="Aptos"><a:majorFont><a:latin typeface="Aptos Display"/></a:majorFont><a:minorFont><a:latin typeface="Aptos"/></a:minorFont></a:fontScheme>
    <a:fmtScheme name="SQE"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme>
  </a:themeElements>
</a:theme>
"""


def doc_props():
    core = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>Selective Query-Side Expansion</dc:title>
  <dc:creator>Salomon DIEI</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
</cp:coreProperties>
"""
    app = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>PowerPoint</Application>
</Properties>
"""
    return core, app


def title(shapes, text, subtitle=None):
    shapes.append(text_box(10, "Title", x(0.55), x(0.34), x(12.1), x(0.62), [text], size=30, bold_first=True))
    if subtitle:
        shapes.append(text_box(11, "Subtitle", x(0.58), x(0.98), x(11.8), x(0.34), [subtitle], size=15, color="muted"))
    shapes.append(line(12, x(0.58), x(1.36), x(12.72), x(1.36), color="line", width=12000))


def footer(shapes, num):
    shapes.append(text_box(900, "Footer", x(0.58), x(7.12), x(10.6), x(0.18), ["Selective Query-Side Expansion for Agent Memory Retrieval"], size=8, color="muted"))
    shapes.append(text_box(901, "Slide number", x(12.1), x(7.12), x(0.55), x(0.18), [str(num)], size=8, color="muted", align="r"))


def card(shape_id, left, top, width, height, heading, body, fill="white", accent="blue"):
    parts = [
        shape(shape_id, f"{heading} card", left, top, width, height, fill=fill, line="line", radius=True),
        shape(shape_id + 1, f"{heading} accent", left, top, x(0.09), height, fill=accent, line=accent),
        text_box(shape_id + 2, f"{heading} heading", left + x(0.22), top + x(0.18), width - x(0.36), x(0.28), [heading], size=18, color="ink", bold_first=True),
        text_box(shape_id + 3, f"{heading} body", left + x(0.22), top + x(0.56), width - x(0.42), height - x(0.68), body, size=14, color="muted"),
    ]
    return "".join(parts)


def make_slides():
    seed = load_seed42()
    multiseed_rows = table_rows(MULTISEED)
    paired_rows = table_rows(PAIRED)
    dense = seed["Dense-Only"]
    sqe = seed["Selective-QE"]
    hybrid = seed["Hybrid-RRF"]
    random_gate = seed["Random-Gated-Expansion"]

    slides = []
    slide_images = []

    # 1. Title.
    shapes = [
        shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white"),
        shape(3, "Accent", 0, 0, x(0.18), SLIDE_H, fill="blue", line="blue"),
        text_box(4, "Main title", x(0.8), x(1.65), x(11.5), x(1.25), ["Selective Query-Side Expansion", "for Agent Memory Retrieval"], size=36, bold_first=True),
        text_box(5, "Subtitle", x(0.84), x(3.08), x(10.8), x(0.72), ["A practical way to recover memories when agent logs and user questions use different language"], size=20, color="muted"),
        text_box(6, "Author", x(0.86), x(5.35), x(9.0), x(0.6), ["Salomon DIEI", "School of Computer Science and Engineering, KOREATECH"], size=16, color="ink", bold_first=True),
    ]
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 2. One-slide overview.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "The talk in one minute")
    shapes.append(card(20, x(0.75), x(1.75), x(3.75), x(3.9), "Problem", ["Useful past memories exist,", "but retrieval misses them", "because logs and questions", "use different words."], fill="blue_light", accent="blue"))
    shapes.append(card(30, x(4.85), x(1.75), x(3.75), x(3.9), "Idea", ["When retrieval looks uncertain,", "ask the memory index with", "execution-style traces and", "paraphrased queries."], fill="orange_light", accent="orange"))
    shapes.append(card(40, x(8.95), x(1.75), x(3.75), x(3.9), "Result", ["Retrieval-only evidence:", "SQE is close to dense retrieval", "and better than Hybrid-RRF,", "but end-to-end Pass@1 is pending."], fill="green_light", accent="green"))
    footer(shapes, 2)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 3. Motivation.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "Why agent memory retrieval fails")
    shapes.append(card(20, x(0.85), x(1.85), x(5.2), x(1.65), "What is stored", ["Terminal outputs", "Stack traces", "Test failures", "Patch diffs"], fill="gray", accent="blue"))
    shapes.append(card(30, x(7.25), x(1.85), x(5.2), x(1.65), "What is asked later", ["Natural-language questions", "High-level bug descriptions", "Short reminders", "Issue summaries"], fill="gray", accent="orange"))
    shapes.append(line(45, x(6.18), x(2.68), x(7.15), x(2.68), color="muted", width=22000, arrow=True))
    shapes.append(text_box(50, "Takeaway", x(1.15), x(4.45), x(11.0), x(1.0), ["The memory may be present, but the query does not look like the memory."], size=26, color="ink", bold_first=True, align="c"))
    footer(shapes, 3)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 4. Method intuition.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "The simple intuition")
    shapes.append(text_box(20, "Sentence", x(0.9), x(1.8), x(11.7), x(0.65), ["Ask the memory index in the language the memory was written in."], size=30, color="ink", bold_first=True, align="c"))
    shapes.append(card(30, x(1.0), x(3.0), x(3.2), x(1.75), "1. Try normal retrieval", ["Use the original question first.", "If confidence is high,", "do not spend extra compute."], fill="blue_light", accent="blue"))
    shapes.append(card(40, x(5.05), x(3.0), x(3.2), x(1.75), "2. Expand only if needed", ["Generate execution-style", "traces and paraphrases", "for low-confidence queries."], fill="orange_light", accent="orange"))
    shapes.append(card(50, x(9.1), x(3.0), x(3.2), x(1.75), "3. Fuse the results", ["Retrieve variants in parallel", "and combine rankings with", "Reciprocal Rank Fusion."], fill="green_light", accent="green"))
    footer(shapes, 4)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 5. Method figure.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "How SQE works")
    shapes.append(image_pic(20, "Method overview", "rId2", x(0.65), x(1.65), x(12.0), x(4.7)))
    shapes.append(text_box(30, "Caption", x(0.95), x(6.45), x(11.3), x(0.35), ["The memory store is unchanged. Only the query is expanded when the first retrieval result looks uncertain."], size=14, color="muted", align="c"))
    footer(shapes, 5)
    slides.append(slide_xml(shapes))
    slide_images.append(["method_overview.png"])

    # 6. Evaluation design.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "Evaluation design")
    metrics = [
        ("5,000", "memory episodes per seed"),
        ("500", "query-memory pairs per seed"),
        ("8", "independent memory-index seeds"),
        ("4,000", "paired query rows in aggregate"),
    ]
    for i, (big, label) in enumerate(metrics):
        left = x(0.85 + i * 3.05)
        shapes.append(shape(20 + i, "Metric card", left, x(1.75), x(2.65), x(1.35), fill="gray", line="line", radius=True))
        shapes.append(text_box(40 + i, "Metric value", left, x(1.98), x(2.65), x(0.42), [big], size=30, color="blue", bold_first=True, align="c"))
        shapes.append(text_box(50 + i, "Metric label", left + x(0.12), x(2.5), x(2.4), x(0.42), [label], size=13, color="muted", align="c"))
    shapes.append(card(70, x(1.0), x(4.0), x(5.25), x(1.65), "Metric used today", ["Recall@5: does the target memory appear in the top five retrieved memories?"], fill="blue_light", accent="blue"))
    shapes.append(card(80, x(7.05), x(4.0), x(5.25), x(1.65), "Important boundary", ["This is a retrieval study. Agent Pass@1 task success has not been measured yet."], fill="orange_light", accent="orange"))
    footer(shapes, 6)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 7. Main result.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "Main retrieval result")
    cards = [
        ("Dense", pct(dense["recall@5"]), "strong baseline", "blue"),
        ("SQE", pct(sqe["recall@5"]), "selective expansion", "orange"),
        ("Hybrid-RRF", pct(hybrid["recall@5"]), "sparse+dense fusion", "green"),
    ]
    for i, (name, value, label, accent) in enumerate(cards):
        left = x(1.0 + i * 4.1)
        shapes.append(shape(20 + i, name, left, x(1.85), x(3.35), x(2.0), fill=f"{accent}_light" if accent != "blue" else "blue_light", line="line", radius=True))
        shapes.append(text_box(40 + i, name + " title", left, x(2.08), x(3.35), x(0.38), [name], size=18, color="ink", bold_first=True, align="c"))
        shapes.append(text_box(50 + i, name + " value", left, x(2.55), x(3.35), x(0.62), [value], size=34, color=accent, bold_first=True, align="c"))
        shapes.append(text_box(60 + i, name + " label", left, x(3.23), x(3.35), x(0.35), [label], size=13, color="muted", align="c"))
    shapes.append(text_box(80, "Interpretation", x(1.1), x(4.65), x(11.2), x(0.92), ["Interpretation: SQE is competitive with dense retrieval and clearly above Hybrid-RRF in the seed-42 audit run, but it does not beat the strongest baseline there."], size=18, color="ink", align="c"))
    footer(shapes, 7)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 8. Bar chart.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "Method comparison")
    shapes.append(image_pic(20, "Recall chart", "rId2", x(0.8), x(1.6), x(11.8), x(4.8)))
    shapes.append(text_box(30, "Caption", x(0.95), x(6.45), x(11.3), x(0.35), ["The key comparison is retrieval quality, not final software-task success."], size=14, color="muted", align="c"))
    footer(shapes, 8)
    slides.append(slide_xml(shapes))
    slide_images.append(["recall_at_5.png"])

    # 9. Multi-seed result.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "Across independent memory seeds")
    shapes.append(card(20, x(0.9), x(1.7), x(3.5), x(1.75), "Mean Recall@5", ["SQE: 69.4%", "Dense: 68.5%", "Always-expand: 69.2%", "Random-gated: 68.9%"], fill="green_light", accent="green"))
    shapes.append(card(30, x(4.9), x(1.7), x(3.5), x(1.75), "Paired effect", ["SQE vs Dense:", "+0.9 points", "95% interval: [0.1, 1.7]"], fill="blue_light", accent="blue"))
    shapes.append(card(40, x(8.9), x(1.7), x(3.5), x(1.75), "Budget control", ["SQE vs Random-gated:", "+0.5 points", "interval crosses zero"], fill="orange_light", accent="orange"))
    shapes.append(text_box(55, "Bottom line", x(1.0), x(4.55), x(11.2), x(0.9), ["Bottom line: the current evidence supports a small retrieval-only difference, not a strong end-to-end performance claim."], size=22, color="ink", bold_first=True, align="c"))
    footer(shapes, 9)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 10. Gate diagnostic.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "What did not work yet: the confidence gate")
    shapes.append(image_pic(20, "Gate diagnostic", "rId2", x(0.7), x(1.62), x(7.0), x(3.95)))
    shapes.append(card(30, x(8.05), x(1.9), x(4.45), x(1.35), "Finding", ["The dense top-1 score does not separate easy and hard retrieval cases cleanly."], fill="orange_light", accent="orange"))
    shapes.append(card(40, x(8.05), x(3.55), x(4.45), x(1.35), "Implication", ["The method idea is plausible, but the gate needs stronger calibration before a top-tier claim."], fill="gray", accent="blue"))
    footer(shapes, 10)
    slides.append(slide_xml(shapes))
    slide_images.append(["gate_diagnostic.png"])

    # 11. What can be claimed.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "What I can claim today")
    shapes.append(card(20, x(0.95), x(1.75), x(5.5), x(3.45), "Supported by the current data", ["SQE can be added at retrieval time.", "It leaves memory writing unchanged.", "It reduces expansion calls relative to always-expand.", "It gives a small Recall@5 gain over dense retrieval across seeds."], fill="green_light", accent="green"))
    shapes.append(card(30, x(6.9), x(1.75), x(5.5), x(3.45), "Not claimed yet", ["No Pass@1 agent-success result yet.", "No human-audited query-label result yet.", "No clear advantage over the random-gated budget control.", "The gate is not solved."], fill="orange_light", accent="orange"))
    footer(shapes, 11)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 12. Next steps.
    shapes = [shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white")]
    title(shapes, "Next steps before submission")
    next_steps = [
        ("1", "Run downstream Pass@1", "Measure whether retrieved memories actually help solve software tasks."),
        ("2", "Collect human labels", "Audit whether generated queries match realistic user or agent questions."),
        ("3", "Improve the gate", "Train or validate a selector using score margin, dense-sparse agreement, and query features."),
        ("4", "Release artifacts", "Publish code and dataset package with the GitHub and Hugging Face links."),
    ]
    for i, (num, head, body) in enumerate(next_steps):
        top = x(1.65 + i * 1.15)
        shapes.append(shape(20 + i, "Number", x(1.0), top, x(0.52), x(0.52), fill="blue", line="blue", radius=True, text=num, size=16, color="white", bold=True, align="c"))
        shapes.append(text_box(40 + i, "Step", x(1.75), top - x(0.02), x(10.5), x(0.28), [head], size=18, color="ink", bold_first=True))
        shapes.append(text_box(60 + i, "Step body", x(1.75), top + x(0.34), x(10.5), x(0.32), [body], size=13, color="muted"))
    footer(shapes, 12)
    slides.append(slide_xml(shapes))
    slide_images.append([])

    # 13. Closing.
    shapes = [
        shape(2, "Background", 0, 0, SLIDE_W, SLIDE_H, fill="white", line="white"),
        text_box(10, "Question", x(1.0), x(2.2), x(11.3), x(0.9), ["Thank you"], size=44, color="ink", bold_first=True, align="c"),
        text_box(11, "Contact", x(1.0), x(3.35), x(11.3), x(0.6), ["Salomon DIEI | salomon@koreatech.ac.kr"], size=18, color="muted", align="c"),
        text_box(12, "Takeaway", x(1.0), x(5.05), x(11.3), x(0.55), ["Takeaway: SQE is a practical retrieval-time idea, but the honest result is a modest retrieval signal and clear next experiments."], size=18, color="blue", align="c"),
    ]
    slides.append(slide_xml(shapes))
    slide_images.append([])

    notes = [
        "# SQE Conference Talk Speaker Notes",
        "",
        "Talk date: May 16, 2026.",
        "",
        "1. Title: introduce SQE as a retrieval-time method for long-horizon agent memory.",
        "2. One-minute overview: explain problem, idea, and honest result.",
        "3. Motivation: make clear that the memory can exist but still be missed because wording differs.",
        "4. Intuition: the phrase to repeat is: ask the memory index in the language the memory was written in.",
        "5. Method: emphasize unchanged memory store and selective expansion only for low-confidence retrieval.",
        "6. Evaluation: define Recall@5 simply. Do not imply this is agent task success.",
        "7. Main result: seed-42 audit anchor. SQE is competitive, not a win over dense there.",
        "8. Method comparison: use this figure to explain baselines at a high level.",
        "9. Multi-seed result: strongest current evidence is small retrieval-only gain over dense, no clear win over random-gated budget control.",
        "10. Gate diagnostic: state the current weakness plainly. The top-1 confidence signal is not enough.",
        "11. Claims: separate supported claims from not-yet-supported claims.",
        "12. Next steps: Pass@1, human labels, better gate, public release.",
        "13. Closing: invite questions around retrieval, evaluation, and deployment.",
    ]

    return slides, slide_images, "\n".join(notes) + "\n"


def build_pptx():
    OUT.mkdir(parents=True, exist_ok=True)
    slides, slide_images, notes = make_slides()
    pptx_path = OUT / "sqe_conference_talk.pptx"
    notes_path = OUT / "sqe_conference_speaker_notes.md"

    images_needed = []
    for names in slide_images:
        for name in names:
            if name not in images_needed:
                images_needed.append(name)

    with zipfile.ZipFile(pptx_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types(len(slides), images_needed))
        z.writestr("_rels/.rels", root_rels())
        z.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        z.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        z.writestr("ppt/slideMasters/slideMaster1.xml", master_xml())
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", master_rels())
        z.writestr("ppt/slideLayouts/slideLayout1.xml", layout_xml())
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", layout_rels())
        z.writestr("ppt/theme/theme1.xml", theme_xml())
        core, app = doc_props()
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)

        for i, (xml, images) in enumerate(zip(slides, slide_images), start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", xml)
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", slide_rels(images))

        for name in images_needed:
            src = FIGURES / name
            if not src.exists():
                raise FileNotFoundError(src)
            z.write(src, f"ppt/media/{name}")

    notes_path.write_text(notes)
    return pptx_path, notes_path


if __name__ == "__main__":
    pptx, notes = build_pptx()
    print(json.dumps({"pptx": str(pptx), "notes": str(notes)}, indent=2))
