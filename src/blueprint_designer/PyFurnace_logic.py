"""
pyFuRNAce backend for Blueprint Designer.

This is the ONLY module that may import pyfurnace (or the rope-* tools or
fill_blueprint).  The GUI talks to it through the small API below, so a
different backend can be dropped in by writing another module that provides
the same names and changing one import line in the GUI.

Backend contract
----------------
Constants / data
    SPECS            {motif_name: [Param, ...]}
    COLORS           {motif_name: "#rrggbb"}
    RESIZE_PARAM     {motif_name: param_name} parameter changed by right-edge drag
    TOOLS            {exe: Tool}              external commands in the Tools menu
    BlueprintError   exception raised by blueprint filling / randomizing

Functions
    motif_names()                          -> list[str]
    specs(name)                            -> list[Param]
    default_values(name)                   -> dict
    is_decorative(name)                    -> bool
    row_span(name)                         -> int
    build_motif(name, values, rot, flip)   -> BuiltMotif     (raises on bad input)
    assemble(rows, align)                  -> Assembly       (raises on failure)
    fill_blueprint(text, design_text=None) -> (text, warnings)
    randomize_blueprint(text)              -> text
    find_exe(name)                         -> str
"""
from __future__ import annotations

import os
import random
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pyfurnace as pf

from fill_blueprint import (BlueprintError, IUPAC,
                             fill_blueprint as _fill_blueprint,
                             parse_origami)

__all__ = [
    "Param", "Opt", "Tool", "BuiltMotif", "Assembly", "BlueprintError",
    "SPECS", "COLORS", "RESIZE_PARAM", "TOOLS",
    "motif_names", "specs", "default_values", "is_decorative", "row_span",
    "build_motif", "assemble", "fill_blueprint", "randomize_blueprint",
    "find_exe",
]

# --------------------------------------------------------------------------- #
# Data types shared with the GUI
# --------------------------------------------------------------------------- #

@dataclass
class Param:
    """One editable motif parameter (drives the properties form)."""
    name: str
    kind: str                 # "int" | "float" | "bool" | "str" | "choice"
    default: object
    lo: int = 0
    hi: int = 100
    choices: tuple = ()
    tip: str = ""


@dataclass
class Opt:
    """One command-line option of an external tool (drives OptionsDialog)."""
    flag: str
    label: str
    kind: str                 # "int" | "float" | "str"
    default: object
    tip: str = ""


@dataclass
class Tool:
    exe: str
    title: str
    opts: list[Opt] = field(default_factory=list)
    needs_input: bool = True          # blueprint is written to a file and passed as last arg
    randomize_ambiguous: bool = False  # replace N/K/S... by concrete bases before running
    produces_pdb: bool = False         # results folder contains .pdb files for the 3D viewer


@dataclass
class BuiltMotif:
    """Backend-neutral description of one constructed motif."""
    text: str                          # ASCII drawing
    sequence: str
    structure: str
    edges: dict | None                 # {"L"/"R"/"T"/"B": [(col, row), ...]} or None
    anchor_row: float | None
    native: object = None              # the backend's own object (GUI never touches it)

    def __str__(self):
        return self.text


@dataclass
class Assembly:
    """Backend-neutral description of an assembled design."""
    sequence: str
    structure: str
    text: str                          # drawing of the whole design
    native: object = None


# --------------------------------------------------------------------------- #
# Motif catalogue
# --------------------------------------------------------------------------- #

NONE = []
OPEN_LEFT = Param("open_left", "bool", False, tip="Flip so the loop opens to the left")
SEQ = Param("sequence", "str", "", tip="5'->3'. Empty = unspecified (N)")
KL = [OPEN_LEFT, SEQ,
      Param("pk_index", "str", "0",
            tip="Kissing partners share an index: '1' pairs with \"1'\"")]
KD = [SEQ,
      Param("pk_index", "str", "0",
            tip="Kissing partners share an index: '1' pairs with \"1'\""),
      Param("Energy", "float", "-8.5")]

START_END_STEM = [
    Param("up_left", "str", "3", tip="position of the 3' end"),
    Param("up_right", "str", "5", tip="position of the 5' end"),
    Param("down_left", "str", "-"),
    Param("down_right", "str", "-"),
]

SINGLE_STRAND = [
    Param("sequence", "str", "", tip="Top strand, 5'->3'. Empty = unspecified"),
    Param("loop", "bool", False,
          tip="If True, the single-stranded region forms a loop. Default is False."),
]

_ALL_SPECS = {
    "Stem": [
        Param("length", "int", 11, 1, 100, tip="Base pairs (ignored if a sequence is given)"),
        Param("sequence", "str", "", tip="Top strand, 5'->3'. Empty = unspecified"),
        Param("wobble_interval", "int", 5, 0, 50, tip="Wobble pair about every N bp (0 = none)"),
        Param("wobble_tolerance", "int", 2, 0, 20, tip="Random +/- variation of the interval"),
        Param("wobble_insert", "choice", "middle", choices=("middle", "start", "end")),
        Param("strong_bases", "bool", True, tip="Prefer strong (G/C) bases"),
    ],
    "Dovetail": [
        Param("length", "int", -1, -20, 20, tip="Sign sets the dovetail direction"),
        Param("sequence", "str", "", tip="Top strand, 5'->3'. Empty = unspecified"),
        Param("up_cross", "bool", True),
        Param("down_cross", "bool", True),
    ],
    "Loop": [OPEN_LEFT, SEQ],
    "TetraLoop": [OPEN_LEFT, Param("sequence", "str", "UUCG", tip="Exactly 4 nt")],
    "KissingLoop120": KL,
    "KissingLoop180": KL,
    "BranchedKissingLoop": KL,
    "KissingDimer": KD,
    "AlphaKissingLoop": KL,
    "Ispinach": NONE,
    "Mango": [OPEN_LEFT],
    "MalachiteGreen": [OPEN_LEFT],
    "MalachiteGreenShort": NONE,
    "Broccoli": NONE,
    "OrangeBroccoli": NONE,
    "RedBroccoli": NONE,
    "Pepper": NONE,
    "Biotin": NONE,
    "PIP3": [OPEN_LEFT],
    "PIP3_mut1": [OPEN_LEFT],
    "PIP3_mut3": [OPEN_LEFT],
    "PIP3_mut5": [OPEN_LEFT],
    "MS2": [OPEN_LEFT],
    "PP7": [OPEN_LEFT],
    "TAR_TAT": [OPEN_LEFT],
    "L7Ae": NONE,
    "Streptavidin": [OPEN_LEFT],
    "Thrombin_exosite1": [OPEN_LEFT],
    "Thrombin_exosite2": [OPEN_LEFT],
    "LambdaTurn": NONE,
    "ThreeWayJunction": NONE,
    "Bend90": NONE,
    "KissingDimer120": KD,
    "BranchedDimer": KD,
    "AlphaKissingDimer": KD,
    "start_end_stem": START_END_STEM,
    "single_strand": SINGLE_STRAND,
    "vertical_link": NONE,
    "vertical_double_link": NONE,
}

# Only offer classes this pyFuRNAce version actually exports.
_AVAILABLE = [n for n in _ALL_SPECS if hasattr(pf, n)]
print("Skipped (not found in pf):", [n for n in _ALL_SPECS if n not in _AVAILABLE])
SPECS = {n: _ALL_SPECS[n] for n in _AVAILABLE}

COLORS = {
    "Stem": "#9ecae1", "Dovetail": "#dadaeb", "Loop": "#c7e9c0",
    "TetraLoop": "#c7e9c0", "KissingLoop120": "#fdae6b",
    "KissingLoop180": "#fdae6b", "BranchedKissingLoop": "#f35a43",
    "KissingDimer": "#a0e725", "AlphaKissingLoop": "#255fe7", "Ispinach": "#25e728",
    "Mango": "#e7c725", "MalachiteGreen": "#00bc03", "MalachiteGreenShort": "#25e728",
    "Broccoli": "#039e05", "OrangeBroccoli": "#dfb10a", "RedBroccoli": "#e72525",
    "Pepper": "#a40c07", "Biotin": "#b9aeff", "PIP3": "#25e728",
    "PIP3_mut1": "#25e728", "PIP3_mut3": "#25e728", "PIP3_mut5": "#25e728",
    "MS2": "#82ffdaff", "PP7": "#689339", "TAR_TAT": "#2b9274", "L7Ae": "#f9baff",
    "Streptavidin": "#e725b3", "Thrombin_exosite1": "#F7C0FF",
    "Thrombin_exosite2": "#b172f8ff", "LambdaTurn": "#e725b3",
    "ThreeWayJunction": "#e725b3", "Bend90": "#e725b3", "KissingDimer120": "#e725b3",
    "BranchedDimer": "#e725b3", "AlphaKissingDimer": "#fa46ca",
    "start_end_stem": "#e725b3", "single_strand": "#e725b3",
    "vertical_link": "#e725b3", "vertical_double_link": "#e725b3",
}

# Which parameter a right-edge drag changes (1 character = 1 bp).
RESIZE_PARAM = {"Stem": "length", "Dovetail": "length"}

# Drawn with pyFuRNAce but not part of the assembled RNA/Origami model.
_DECORATIVE = {"vertical_link", "vertical_double_link"}


def motif_names():
    return list(_AVAILABLE)


def specs(name):
    return SPECS[name]


def default_values(name):
    return {p.name: p.default for p in SPECS[name]}


def is_decorative(name):
    return name in _DECORATIVE


def row_span(name):
    """Number of blueprint rows occupied by this motif."""
    return 2 if name == "AlphaKissingLoop" else 1


# --------------------------------------------------------------------------- #
# Building motifs
# --------------------------------------------------------------------------- #

def _build_kwargs(cls_name, values):
    kw = dict(values)
    seq = kw.get("sequence", "").strip().upper()
    if seq:
        kw["sequence"] = seq
        if cls_name in ("Stem", "Dovetail"):
            n = kw.pop("length", 0)          # length comes from the sequence
            if cls_name == "Dovetail":
                kw["sign"] = -1 if n < 0 else 1
    else:
        kw.pop("sequence", None)
    return kw


def _xy(p):
    try:
        return int(p[0]), int(p[1])
    except Exception:
        return int(p.x), int(p.y)


def _junction_edges(motif):
    """Junction cells grouped by edge (L/R/T/B), or None if unavailable."""
    try:
        out = {"L": [], "R": [], "T": [], "B": []}
        for direction, positions in motif.junctions.items():
            dx, dy = _xy(direction)
            if dx > 0 and dy == 0:
                edge = "R"
            elif dx < 0 and dy == 0:
                edge = "L"
            elif dx == 0 and dy < 0:
                edge = "T"
            elif dx == 0 and dy > 0:
                edge = "B"
            else:
                continue                      # diagonal / zero direction
            out[edge] = sorted(_xy(p) for p in positions)
        return out
    except Exception:
        return None


def _anchor_row(edges):
    """Central row of the left/right junctions (motif text-grid coordinates)."""
    if not edges:
        return None
    rows = [y for e in ("L", "R") for _, y in edges[e]]
    if not rows:
        return None
    return (min(rows) + max(rows)) / 2


def _safe_str(obj, attr):
    try:
        return str(getattr(obj, attr))
    except Exception:
        return ""


def build_motif(cls_name, values, rot=0, flipped=False) -> BuiltMotif:
    """Construct a motif. Raises if the parameters are invalid."""
    m = getattr(pf, cls_name)(**_build_kwargs(cls_name, values))
    if rot:
        r = m.rotate(rot)
        m = r if r is not None else m
    if flipped:
        r = m.flip(horizontally=True, vertically=False)
        m = r if r is not None else m
    try:
        text = str(m).rstrip("\n")
    except Exception:
        text = cls_name
    edges = _junction_edges(m)
    return BuiltMotif(
        text=text,
        sequence=_safe_str(m, "sequence"),
        structure=_safe_str(m, "structure"),
        edges=edges,
        anchor_row=_anchor_row(edges),
        native=m,
    )


def assemble(rows, align="center") -> Assembly:
    """rows: list of rows, each a list of BuiltMotif (left to right)."""
    ori = pf.Origami([[b.native for b in row] for row in rows],
                     align=align, copy=True)
    return Assembly(
        sequence=str(ori.sequence),
        structure=str(ori.structure),
        text=str(ori),
        native=ori,
    )


# --------------------------------------------------------------------------- #
# Blueprint text helpers
# --------------------------------------------------------------------------- #

def fill_blueprint(text, design_text=None):
    """Return (blueprint_text, warnings). Raises BlueprintError."""
    res = _fill_blueprint(text) if design_text is None else _fill_blueprint(text, design_text)
    return res.text(), list(getattr(res, "warnings", []) or [])


_PAIRS = [("A", "U"), ("U", "A"), ("G", "C"), ("C", "G"), ("G", "U"), ("U", "G")]
_OPEN, _CLOSE = "([{<", ")]}>"


def _allowed(code):
    if code in "ACGU":
        return set(code)
    return set(IUPAC.get(code, "ACGU"))


def randomize_blueprint(text, rng=random):
    """Replace every ambiguous letter (N, K, S, ...) with a random nucleotide.

    Paired positions get complementary bases (incl. G-U wobble), so stems stay
    valid. Fixed A/C/G/U letters are kept.
    """
    lines = text.splitlines()
    p = parse_origami(lines)
    template, struct = p.seq, p.struct
    if struct is None:
        raise BlueprintError("No 'Structure:' line found.")
    if len(template) != len(struct):
        raise BlueprintError("Sequence and Structure have different lengths.")

    seq = [None] * len(template)

    # pairs first (one stack per bracket type)
    stacks = {c: [] for c in _OPEN}
    for j, ch in enumerate(struct):
        if ch in _OPEN:
            stacks[ch].append(j)
        elif ch in _CLOSE:
            i = stacks[_OPEN[_CLOSE.index(ch)]].pop()
            ok = [(a, b) for a, b in _PAIRS
                  if a in _allowed(template[i]) and b in _allowed(template[j])]
            if ok:
                seq[i], seq[j] = rng.choice(ok)

    # everything else (unpaired, or pairs that had no valid choice)
    for k, code in enumerate(template):
        if seq[k] is None:
            seq[k] = rng.choice(sorted(_allowed(code)))

    design = f"sequence : {''.join(seq)}\ntarget : {struct}\n"
    return _fill_blueprint(text, design).text()


# --------------------------------------------------------------------------- #
# External rope-* command-line tools
# --------------------------------------------------------------------------- #

CPUS = os.cpu_count() or 1
RUNS = Opt("-r", "Runs", "int", 3)
WORKERS = Opt("-w", "Workers/threads", "int", min(4, CPUS))

TOOLS = {t.exe: t for t in [
    Tool("rope-fold", "Predict sequences (batch)", [RUNS, WORKERS]),
    Tool("rope-dragon", "Predict sequences (continuous)",
         [RUNS, WORKERS,
          Opt("-e", "Ensemble diversity (ED)", "float", 0.0),
          Opt("-t", "Time per run", "float", 60.0)]),
    Tool("rope-build", "Build PDB files",
         [Opt("--ligand", "Ligand (MODULE=LIGAND)", "str", "")],
         randomize_ambiguous=True, produces_pdb=True),
    Tool("rope-flip", "Flip blueprint"),
]}


def find_exe(name: str) -> str:
    """PATH first, then the scripts folder of the running interpreter."""
    found = shutil.which(name)
    if found:
        return found
    exe_dir = Path(sys.executable).parent
    for cand in (exe_dir / name, exe_dir / f"{name}.exe",
                 exe_dir / "Scripts" / f"{name}.exe"):
        if cand.exists():
            return str(cand)
    raise FileNotFoundError(
        f"{name} not found. Is the package installed in this environment?")