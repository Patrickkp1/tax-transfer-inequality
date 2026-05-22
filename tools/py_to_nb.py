"""
Convert each .py script in the project into a Jupyter notebook with sensible
cell boundaries based on the existing section markers in the code.

Strategy:
  1. Top-of-file docstring -> first markdown cell
  2. Imports -> single code cell
  3. Each major section (delimited by '# ====' or '# ----' headers) -> one
     code cell, with the header text as a preceding markdown cell.
"""
import os
import re
import nbformat as nbf

# ----------------------------------------------------------------------------
# Mapping: source script (workspace) -> output notebook name (notebooks/)
# ----------------------------------------------------------------------------
SCRIPTS = [
    ("build_earned_income_panel-9.py",            "01_build_earned_income_panel.ipynb"),
    ("transfer_distribution_panel-2.py",          "02_transfer_distribution_panel.ipynb"),
    ("tax_distribution_panel-8.py",               "03_tax_distribution_panel.ipynb"),
    ("income_after_taxes_transfers_panel-6.py",   "04_income_after_taxes_transfers_panel.ipynb"),
    ("top_percentile_taxes_transfers_panel-7.py", "05_top_percentile_taxes_transfers_panel.ipynb"),
    ("income_visualizations-4.py",                "06_income_visualizations.ipynb"),
    ("charts_5_6_ultra_top-5.py",                 "07_charts_5_6_ultra_top.ipynb"),
    ("report_figures-3.py",                       "08_report_figures.ipynb"),
    ("cpi_bias_adjusted_v3_dbpi.py",              "09_cpi_bias_adjusted_v3_dbpi.ipynb"),
]

WORKSPACE = "/home/user/workspace"
OUT_DIR   = os.path.join(WORKSPACE, "notebooks")
os.makedirs(OUT_DIR, exist_ok=True)


# Section heading regex: matches '# =====' or '# -----' bars (>= 30 chars
# of '=' or '-', possibly with surrounding '#').  These are how every script
# in the project marks its sections.
# Match bar-comment lines: '#=====', '# -----', or unicode box bars like
# '# ═══' (used in cpi_bias_adjusted_v3_dbpi.py).
SECTION_BAR = re.compile(r"^\s*#\s*[=\-\u2550\u2500\u2501\u2576-\u257F]{15,}\s*$")


def split_cells(src: str):
    """
    Yield ('markdown', text) or ('code', text) tuples.

    Detection rules:
      * The leading triple-quoted docstring (if present) becomes the first
        markdown cell.
      * Each pair of bar comment lines (===== ... heading ... =====) plus the
        text between them becomes a markdown cell that introduces the next
        code cell.
      * All other code lines accumulate into a code cell that flushes when
        the next bar comment block starts.
    """
    lines = src.split("\n")
    i = 0

    # --- 0. Skip shebang line (#!/usr/bin/env python3) if present ---
    if i < len(lines) and lines[i].startswith("#!"):
        i += 1

    # --- 1. Docstring (between first """ and the matching """) ---
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i < len(lines) and lines[i].lstrip().startswith('"""'):
        start = i
        # Single-line docstring:  """foo"""
        if lines[i].count('"""') >= 2:
            end = i
        else:
            i += 1
            while i < len(lines) and '"""' not in lines[i]:
                i += 1
            end = i
        ds_text = "\n".join(lines[start:end+1])
        # Strip the opening and closing """
        ds_text = ds_text.strip()
        if ds_text.startswith('"""'): ds_text = ds_text[3:]
        if ds_text.endswith('"""'):   ds_text = ds_text[:-3]
        yield ("markdown", ds_text.strip())
        i = end + 1

    # --- 2. Walk remaining lines, splitting on bar-comment blocks ---
    buf = []

    def flush():
        nonlocal buf
        text = "\n".join(buf).strip()
        if text:
            yield ("code", text)
        buf = []

    while i < len(lines):
        line = lines[i]

        if SECTION_BAR.match(line):
            # Found opening bar; collect comment lines until closing bar
            heading = []
            j = i + 1
            while j < len(lines):
                if SECTION_BAR.match(lines[j]):
                    j += 1
                    break
                # Strip leading "# " from heading lines
                hl = lines[j].lstrip()
                if hl.startswith("# "):  hl = hl[2:]
                elif hl.startswith("#"): hl = hl[1:]
                heading.append(hl.rstrip())
                j += 1

            # Flush any code accumulated so far
            for item in flush():
                yield item

            md_text = "\n".join(heading).strip()
            if md_text:
                # Heuristic: if the heading is one short line, render as ##; else as text
                first_line = md_text.split("\n", 1)[0]
                if len(md_text.split("\n")) == 1 and len(first_line) < 80:
                    yield ("markdown", "## " + first_line)
                else:
                    yield ("markdown", "### " + first_line + "\n\n" + "\n".join(md_text.split("\n")[1:]))
            i = j
            continue

        buf.append(line)
        i += 1

    for item in flush():
        yield item


def make_notebook(cells):
    nb = nbf.v4.new_notebook()
    nb["cells"] = []
    for kind, text in cells:
        if kind == "markdown":
            nb["cells"].append(nbf.v4.new_markdown_cell(text))
        else:
            nb["cells"].append(nbf.v4.new_code_cell(text))
    nb["metadata"] = {
        "kernelspec": {"name": "python3", "display_name": "Python 3"},
        "language_info": {"name": "python"},
    }
    return nb


for src_name, nb_name in SCRIPTS:
    src_path = os.path.join(WORKSPACE, src_name)
    if not os.path.exists(src_path):
        print(f"SKIP: {src_name} not found")
        continue
    with open(src_path) as f:
        src = f.read()
    cells = list(split_cells(src))
    nb = make_notebook(cells)
    out_path = os.path.join(OUT_DIR, nb_name)
    with open(out_path, "w") as f:
        nbf.write(nb, f)
    print(f"  ✓ {nb_name}  ({len(cells)} cells, {sum(1 for k,_ in cells if k=='code')} code)")

print(f"\nWrote {len(os.listdir(OUT_DIR))} notebooks to {OUT_DIR}")
