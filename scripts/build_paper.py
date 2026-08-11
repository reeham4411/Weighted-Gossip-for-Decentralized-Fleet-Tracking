"""
Assemble the complete paper into a single document.

paper/adaptive_gwg_paper.md holds the hand-written sections (I-IV, VIII) with
placeholders for the results sections; paper/RESULTS.md holds Sections V-VII,
generated from results/results.json. This splices them into one file so the
paper can be read, reviewed, or converted without chasing two documents.

    python3 src/gwg_simulation.py            # -> results/results.json
    python3 scripts/make_results_sections.py # -> paper/RESULTS.md
    python3 scripts/build_paper.py           # -> paper/FULL_PAPER.md

Optionally converts to .docx if pandoc is available, since the team's
submission format is Word.
"""

import os
import re
import shutil
import subprocess
import sys

SRC = "paper/adaptive_gwg_paper.md"
RESULTS = "paper/RESULTS.md"
OUT = "paper/FULL_PAPER.md"
FIGURES_DIR = "results/figures"

# The placeholder block that RESULTS.md replaces.
PLACEHOLDER = re.compile(
    r"## V\. Experimental Setup.*?(?=\n---\n\n## VIII\. Conclusion)",
    re.DOTALL,
)

# Matches the caption list entries under "## Figures", e.g.
# "- **fig3_attribution.png** — Contribution attribution: ..."
FIGURE_ENTRY = re.compile(r"^- \*\*(fig(\d+)_\S+\.png)\*\* — (.+)$", re.MULTILINE)


def embed_figures(full):
    """Inline each figure as an image right after its first "Fig. N" mention.

    RESULTS.md only lists figures by filename and caption in a trailing
    "## Figures" section; nothing upstream of that point ever shows the
    reader an actual image. This finds the first paragraph that names each
    figure ("Fig. 3 shows the same decomposition graphically.") and inserts
    the image plus its caption right after that paragraph, in reading order,
    so the assembled paper carries its own figures instead of only
    describing where to find them.
    """
    figures_heading = full.find("\n## Figures\n")
    if figures_heading == -1:
        return full
    body, tail = full[:figures_heading], full[figures_heading:]

    captions = {
        int(num): (fname, caption.strip())
        for fname, num, caption in FIGURE_ENTRY.findall(tail)
    }
    if not captions:
        return full

    paragraphs = body.split("\n\n")
    inserted = set()
    out_paragraphs = []
    for para in paragraphs:
        out_paragraphs.append(para)
        for n in sorted(set(int(m) for m in re.findall(r"Fig\.\s(\d+)", para))):
            if n in inserted or n not in captions:
                continue
            fname, caption = captions[n]
            path = os.path.join(FIGURES_DIR, fname)
            if not os.path.exists(path):
                continue
            out_paragraphs.append(f"![Fig. {n}. {caption}]({path})")
            out_paragraphs.append(f"*Fig. {n}. {caption}*")
            inserted.add(n)
    return "\n\n".join(out_paragraphs) + tail


def main():
    for path in (SRC, RESULTS):
        if not os.path.exists(path):
            raise SystemExit(
                f"{path} not found. Run src/gwg_simulation.py and "
                f"scripts/make_results_sections.py first.")

    body = open(SRC).read()
    results = open(RESULTS).read()
    # Drop the generator's HTML comment header; it is noise in the assembled paper.
    results = re.sub(r"^<!--.*?-->\n", "", results, flags=re.DOTALL | re.MULTILINE).strip()

    if not PLACEHOLDER.search(body):
        raise SystemExit(
            "Could not find the Section V-VII placeholder in " + SRC +
            " -- has the section structure changed?")

    full = PLACEHOLDER.sub(lambda _: results + "\n", body)

    # Strip the working-notes status block: it is guidance for the team, not
    # part of the paper a reviewer should see.
    full = re.sub(r"^> \*\*Status\.\*\*.*?(?=\n---\n)", "", full,
                  flags=re.DOTALL | re.MULTILINE)

    full = embed_figures(full)

    with open(OUT, "w") as fh:
        fh.write(full)
    words = len(full.split())
    print(f"wrote {OUT} ({words:,} words, ~{words/650:.0f} double-column pages)")

    # Guard against submitting under a title the results no longer support.
    title = full.splitlines()[0].lstrip("# ").strip()
    if "Adaptive" in title and "adds nothing measurable" in results:
        print()
        print("  NOTE: the assembled paper is titled")
        print(f"        \"{title}\"")
        print("        but Section VI-B reports that adaptive region management adds")
        print("        nothing measurable over a region-confined fixed grid. Decide the")
        print("        title before submitting -- see the options at the top of")
        print(f"        {SRC}.")
        print()

    if shutil.which("pandoc"):
        docx = OUT.replace(".md", ".docx")
        try:
            subprocess.run(["pandoc", OUT, "-o", docx], check=True)
            print(f"wrote {docx}")
        except subprocess.CalledProcessError as exc:
            print(f"pandoc conversion failed ({exc}); the Markdown is still valid")
    else:
        print("pandoc not installed — skipping .docx. "
              "Install it (brew install pandoc) to get a Word version.")


if __name__ == "__main__":
    sys.exit(main())
