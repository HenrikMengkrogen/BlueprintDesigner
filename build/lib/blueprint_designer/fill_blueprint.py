#!/usr/bin/env python3
"""
blueprint_filler - fill the placeholder letters (N, K, S, ...) of an Origami
blueprint with a designed sequence.  String in, string out.

Origami text (first argument) looks like:

    >Origami

    row 0: TetraLoop  Stem

    ╭CGNNNNKNNNNNN
    │  ┊┊┊┊┊┊┊┊┊┊┊
    ╰UUNNNNKNNNNNN

    Sequence:
    NNNNNNKNNNNUUCGNNNNKNNNNNN

    Structure:
    (((((((((((....)))))))))))

Design text (second argument, optional) is the design-tool output, with one
or more result blocks:

    ==== FINAL (run 1) ====
    sequence : GCGAGCGGACCUUCGGGUCUGCUCGC
    target   : (((((((((((....)))))))))))
    bp_distance : 0

The blueprint is a 2D drawing, so letters are NOT in 5'->3' order when read
left-to-right.  The strand is traced from one end to the other (through
corners and crossings) and the i-th visited nucleotide cell receives
sequence[i].

Which end is the 5' end?
    * If the drawing contains '5' and '3' markers, they are used.
    * Otherwise the ends are located from the sequence: every run of strand that is
      exactly as long as the sequence is a candidate (5'->3' and 3'->5'), and the
      candidates are narrowed by comparing the first/last k letters with the
      Sequence line (fixed letters, IUPAC codes), k = 1, 2, 4, ... until one is left.
      The found ends get '5' / '3' markers in the output (mark_ends=True).
      If the strand is broken, the error says how far it could be followed and
      where it stopped. If both orientations fit equally well, add markers by hand.

Usage
-----
    from blueprint_filler import fill_blueprint, BlueprintError

    try:
        res = fill_blueprint(origami_text, design_text, run=1)
    except BlueprintError as e:
        ...

    res.text()                      # full file with Sequence/Structure/drawing filled
    res.text(blueprint_only=True)   # only the drawing
    res.sequence, res.structure     # what was used
    res.path                        # [(row, col), ...] nucleotide cells, 5'->3'
    res.warnings                    # fixed-base conflicts / IUPAC violations

Command line (for testing)
    python blueprint_filler.py origami.txt [design.txt] [--run N] [-o OUT]
                               [--blueprint-only] [--overwrite-all]
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple, Optional

__all__ = ["BlueprintError", "FillResult", "fill_blueprint",
           "parse_origami", "parse_design", "trace_strand"]

E, W, N, S = (0, 1), (0, -1), (-1, 0), (1, 0)

# corner -> {direction of travel when entering: new direction}
CORNERS = {
    "╭": {W: S, N: E},   # connects east + south
    "╮": {E: S, N: W},   # connects west + south
    "╰": {W: N, S: E},   # connects east + north
    "╯": {E: N, S: W},   # connects west + north
}
HORIZONTAL = set("─")
VERTICAL = set("│|^v↑↓")
FIXED = set("ACGUT")

IUPAC = {
    "N": "ACGU", "K": "GU", "S": "GC", "R": "AG", "Y": "CU",
    "M": "AC", "W": "AU", "B": "CGU", "D": "AGU", "H": "ACU", "V": "ACG",
}

# ">Origami" title line and "row 0: ..." annotation lines are not part of the drawing
_LABEL = re.compile(r"^\s*(>|row\s+\d+\s*:)", re.IGNORECASE)


class BlueprintError(Exception):
    """Raised for any parsing, tracing or consistency problem."""


@dataclass
class FillResult:
    lines: list                  # full output file, line by line
    blueprint: list              # only the filled drawing, line by line
    sequence: str                # sequence that was used
    structure: Optional[str]     # dot-bracket structure used
    path: list                   # [(row, col), ...] nucleotide cells, 5'->3'
    n_filled: int                # cells actually replaced
    warnings: list = field(default_factory=list)
    design_info: Optional[dict] = None   # chosen design block, if a design was given

    @property
    def n_cells(self) -> int:
        return len(self.path)

    @property
    def five_prime(self):          # (row, col) of the 5' end cell in the drawing
        return self.path[0]

    @property
    def three_prime(self):         # (row, col) of the 3' end cell
        return self.path[-1]

    def text(self, blueprint_only: bool = False) -> str:
        return "\n".join(self.blueprint if blueprint_only else self.lines) + "\n"


# --------------------------------------------------------------------------- #
# parsing
# --------------------------------------------------------------------------- #
def _is_nt(ch: str) -> bool:
    return ch.isascii() and ch.isupper()


def _norm(ch: str) -> str:
    return "U" if ch == "T" else ch


class Parsed(NamedTuple):
    seq: str
    seq_i: int                 # line index holding the sequence
    struct: Optional[str]
    struct_i: Optional[int]
    bp_start: int              # drawing = lines[bp_start:bp_end]
    bp_end: int
    seq_prefix: str = ""       # "Sequence: " when the value is on the same line, else ""
    struct_prefix: str = ""


def _read_field(lines: list, i: int):
    """
    Value of a 'Sequence:' / 'Structure:' field, either on the same line after the
    colon ("Sequence: ACGU") or alone on the next line.
    Returns (value, line_index, prefix) or None.
    """
    head, colon, rest = lines[i].partition(":")
    if colon and rest.strip():
        return "".join(rest.split()), i, head + ": "
    if i + 1 < len(lines):
        return "".join(lines[i + 1].split()), i + 1, ""
    return None


def parse_origami(lines: list) -> Parsed:
    """
    Locate Sequence, Structure and the drawing.

    Sequence/Structure may be 'Sequence: ACGU' or 'Sequence:' + value on the next line.
    The drawing is the part below a 'Blueprint:' header (up to 'Folding barriers'),
    or, if there is no such header, every remaining line that is not blank, not a
    '>title' / 'row N:' label and not part of the Sequence/Structure fields -
    wherever they sit in the text (above, below or between them).
    """
    seq = struct = None
    seq_i = struct_i = seq_h = struct_h = None
    seq_prefix = struct_prefix = ""
    bp_start = bp_end = None
    for i, line in enumerate(lines):
        low = line.strip().lower()
        if low.startswith("sequence") and seq is None:
            f = _read_field(lines, i)
            if f:
                seq, seq_i, seq_prefix = f
                seq_h = i
                seq = seq.upper().replace("T", "U")
        elif low.startswith("structure") and struct is None:
            f = _read_field(lines, i)
            if f:
                struct, struct_i, struct_prefix = f
                struct_h = i
        elif low.startswith("blueprint") and bp_start is None:
            bp_start = i + 1
        elif low.startswith("folding barriers") and bp_start is not None:
            bp_end = i
            break
    if seq is None:
        raise BlueprintError("Could not find a 'Sequence:' line.")

    if bp_start is None:                       # headerless layout
        taken = {h for h in (seq_h, seq_i, struct_h, struct_i) if h is not None}
        idx = [i for i, l in enumerate(lines)
               if i not in taken and l.strip() and not _LABEL.match(l)]
        if not idx:
            raise BlueprintError("Could not find a blueprint drawing in the text.")
        bp_start, bp_end = idx[0], idx[-1] + 1
    elif bp_end is None:
        bp_end = len(lines)
    return Parsed(seq, seq_i, struct, struct_i, bp_start, bp_end, seq_prefix, struct_prefix)


def parse_design(text: str, run: int = 1):
    """
    Read the run-th '==== FINAL (run N) ====' block of a design output
    (or the whole text if it has no such headers).
    Returns (sequence, target, block_dict).
    """
    blocks, cur = [], None
    for line in text.splitlines():
        if line.startswith("====") and "FINAL" in line.upper():
            cur = {}
            blocks.append(cur)
        elif ":" in line:
            if cur is None:
                cur = {}
                blocks.append(cur)
            k, v = line.split(":", 1)
            cur.setdefault(k.strip().lower(), v.strip())
    blocks = [b for b in blocks if "sequence" in b and "target" in b]
    if not blocks:
        raise BlueprintError("No 'sequence' / 'target' lines found in the design text.")
    if not 1 <= run <= len(blocks):
        raise BlueprintError(f"run={run} requested but the design has {len(blocks)} result block(s).")
    b = blocks[run - 1]
    return ("".join(b["sequence"].split()).upper().replace("T", "U"),
            "".join(b["target"].split()), b)


# --------------------------------------------------------------------------- #
# tracing
# --------------------------------------------------------------------------- #
def _step_ok(ch: str, d: tuple) -> bool:
    """Can a strand travelling in direction d enter a cell containing ch?"""
    if ch in VERTICAL:
        return d in (N, S)
    if ch in HORIZONTAL:
        return d in (E, W)
    if ch == "┼":
        return True
    if ch in CORNERS:
        return d in CORNERS[ch]
    return _is_nt(ch)


def _walk(at, start: tuple, d: tuple, end: Optional[tuple]) -> list:
    """
    Follow the strand from `start` in direction d.
    end=None : `start` is a '5' marker; stop at the '3' marker.
    end=cell : `start` is itself a nucleotide; stop after visiting `end`.
    """
    r, c = start
    path = [start] if end is not None else []
    seen = set()
    while True:
        r, c = r + d[0], c + d[1]
        ch = at(r, c)
        if end is None and ch == "3":
            return path
        if (r, c, d) in seen:
            raise BlueprintError(f"Strand loops back on itself at row {r}, col {c}.")
        seen.add((r, c, d))

        if ch in VERTICAL:
            if d not in (N, S):
                raise BlueprintError(f"Strand hits '{ch}' sideways at row {r}, col {c}.")
        elif ch in HORIZONTAL:
            if d not in (E, W):
                raise BlueprintError(f"Strand hits '{ch}' vertically at row {r}, col {c}.")
        elif ch == "┼":
            pass                                   # straight through
        elif ch in CORNERS:
            if d not in CORNERS[ch]:
                raise BlueprintError(f"Strand cannot enter corner '{ch}' this way at row {r}, col {c}.")
            d = CORNERS[ch][d]
        elif _is_nt(ch):
            path.append((r, c))
            if (r, c) == end:
                return path
        else:
            raise BlueprintError(f"Strand ran into {ch!r} at row {r}, col {c} (broken path?).")


def _advance(at, r: int, c: int, d: tuple):
    """
    From nucleotide cell (r, c) heading in direction d, go to the next nucleotide cell
    (turning at corners, passing straight over lines and crossings).
    Returns ((r2, c2, d2), None), or (None, (row, col, char)) naming where the strand is blocked.
    """
    seen = set()
    while True:
        r, c = r + d[0], c + d[1]
        ch = at(r, c)
        if _is_nt(ch):
            return (r, c, d), None
        if (r, c, d) in seen:
            return None, (r, c, ch)
        seen.add((r, c, d))
        if ch in CORNERS and d in CORNERS[ch]:
            d = CORNERS[ch][d]
        elif ch == "┼" or (ch in VERTICAL and d in (N, S)) or (ch in HORIZONTAL and d in (E, W)):
            pass
        else:
            return None, (r, c, ch)


@lru_cache(maxsize=None)
def _letters(ch: str) -> frozenset:
    """Nucleotides a drawing cell / template letter allows (unknown symbols allow anything)."""
    ch = _norm(ch)
    if ch in ("A", "C", "G", "U"):
        return frozenset(ch)
    return frozenset(IUPAC.get(ch, "ACGU"))


def _ends_match(grid: list, path: list, template: str, k: int) -> bool:
    """Do the first k and the last k cells of `path` agree with the template's first/last k letters?"""
    n = len(path)
    for i in range(min(k, n)):
        for j in (i, n - 1 - i):
            r, c = path[j]
            if not (_letters(grid[r][c]) & _letters(template[j])):
                return False
    return True


def _find_strand(grid: list, at, template: str, others=()):
    """
    Locate the strand without markers, using the sequence.

    1. Follow the strand from every nucleotide cell in every direction and keep the
       runs that are exactly len(template) cells long. For a clean drawing these are
       the strand read 5'->3' and 3'->5'. (Neighbouring rows touching the end cells do
       not matter, because the strand only turns at corners.)
    2. If several remain, compare the first k and last k cells with the sequence
       ends, doubling k (1, 2, 4, ...) until exactly one run is left.

    Returns (path, heading leaving the first cell, heading arriving at the last cell).
    """
    L = len(template)
    cells = [(r, c) for r, row in enumerate(grid) for c, ch in enumerate(row) if _is_nt(ch)]
    if not cells:
        raise BlueprintError("The drawing contains no nucleotide cells.")

    nxt, blocked, length = {}, {}, {}

    def succ(st):
        if st not in nxt:
            nxt[st], blocked[st] = _advance(at, *st)
        return nxt[st]

    states = [(r, c, d) for r, c in cells for d in (E, W, S, N)]
    for st in states:                                   # run length from every state
        stack, on, cur = [], set(), st
        while cur is not None and cur not in length and cur not in on:
            on.add(cur)
            stack.append(cur)
            cur = succ(cur)
        base = length.get(cur, 0) if cur is not None else 0
        for t in reversed(stack):
            base += 1
            length[t] = base

    starts = [st for st in states if length[st] == L]
    if not starts:
        best = max(states, key=length.get)
        last = best
        for _ in range(length[best] - 1):
            last = succ(last)
        why = blocked.get(last)
        where = (f"stops at drawing row {why[0]}, col {why[1]} (next to {why[2]!r})" if why
                 else "ends there")
        raise BlueprintError(
            f"No strand of {L} nt could be traced in the drawing. The longest strand that can be "
            f"followed has {length[best]} cells (starting at drawing row {best[0]}, col {best[1]}) "
            f"and {where}; the drawing has {len(cells)} nucleotide cells in total. "
            "(Rows/cols are 0-based within the drawing.)"
        )

    candidates = []
    for st in starts:
        cur, path = st, [(st[0], st[1])]
        for _ in range(L - 1):
            cur = succ(cur)
            path.append((cur[0], cur[1]))
        candidates.append((path, st[2], cur[2]))
    if len(candidates) == 1:
        return candidates[0]

    ambiguous = False
    for hint in (template, *[h for h in others if h != template]):
        pool, k = candidates, 1
        while len(pool) > 1:
            pool = [cand for cand in pool if _ends_match(grid, cand[0], hint, k)]
            if k >= L:
                break
            k = min(L, k * 2)
        if len(pool) == 1:
            return pool[0]
        ambiguous = ambiguous or len(pool) > 1
    if ambiguous:
        raise BlueprintError("Cannot tell which end of the strand is the 5' end: all "
                             f"{len(candidates)} possible orientations fit the sequence equally well. "
                             "Add '5' and '3' markers to the drawing.")
    raise BlueprintError("The strand was found, but neither orientation agrees with the fixed "
                         "letters / IUPAC codes of the Sequence line.")


def _trace(grid: list, hints: tuple):
    """
    Returns (path, new_markers). new_markers is None when the drawing already has
    '5'/'3' markers, else the cells just outside the 5' and 3' ends where they belong.
    """
    def at(r, c):
        return grid[r][c] if 0 <= r < len(grid) and 0 <= c < len(grid[r]) else " "

    five = three = None
    for r, row in enumerate(grid):
        for c, ch in enumerate(row):
            if ch == "5":
                five = (r, c)
            elif ch == "3":
                three = (r, c)

    if five and three:                                   # explicit markers
        d = next((cand for cand in (E, W, S, N)
                  if _step_ok(at(five[0] + cand[0], five[1] + cand[1]), cand)), None)
        if d is None:
            raise BlueprintError("The '5' marker is not attached to any strand.")
        return _walk(at, five, d, None), None
    if five or three:
        raise BlueprintError("Found only one of the '5' / '3' markers; the blueprint needs both or neither.")

    if not hints:
        raise BlueprintError("The drawing has no '5' / '3' markers, so a sequence is needed to find the ends.")
    path, d0, dl = _find_strand(grid, at, hints[0], hints[1:])
    (r0, c0), (rl, cl) = path[0], path[-1]
    return path, ((r0 - d0[0], c0 - d0[1]), (rl + dl[0], cl + dl[1]))


def trace_strand(grid: list, *hints: str) -> list:
    """
    Return the (row, col) of every nucleotide cell in 5'->3' order.
    Uses the '5'/'3' markers if the grid has them, otherwise locates the ends with the
    sequence(s) in `hints` (template first).
    """
    return _trace(grid, hints)[0]


# --------------------------------------------------------------------------- #
# main API
# --------------------------------------------------------------------------- #
def fill_blueprint(origami_text: str,
                   design_text: Optional[str] = None,
                   run: int = 1,
                   overwrite_all: bool = False,
                   mark_ends: bool = True) -> FillResult:
    """
    Fill an origami blueprint and return a FillResult.

    origami_text   the origami text (drawing + Sequence + Structure), e.g. Canvas.export()
    design_text    optional design output; its sequence is used only if its
                   target equals the origami file's Structure
    run            which 'FINAL (run N)' block of the design to use
    overwrite_all  also replace fixed A/C/G/U cells (default: keep and check them)
    mark_ends      if the drawing has no '5'/'3' markers and the ends were located from the
                   sequence, write '5' and '3' next to them in the output
    """
    lines = origami_text.splitlines()
    p = parse_origami(lines)
    seq, struct, a, b = p.seq, p.struct, p.bp_start, p.bp_end
    template = seq                     # the Sequence line as written (fixed letters / IUPAC codes)
    warnings: list = []
    info = None

    if design_text is not None:
        new_seq, new_target, info = parse_design(design_text, run)
        if struct is None:
            raise BlueprintError("The origami text has no 'Structure:' line to compare against.")
        if new_target != struct:
            diffs = [i + 1 for i, (x, y) in enumerate(zip(new_target, struct)) if x != y]
            raise BlueprintError(
                "Structure mismatch: the design's target does not match the origami Structure "
                f"(lengths {len(new_target)} vs {len(struct)}"
                + (f", first differences at positions {diffs[:10]}" if diffs else "") + ")."
            )
        if len(new_seq) != len(struct):
            raise BlueprintError(f"Design sequence length {len(new_seq)} != structure length {len(struct)}.")
        seq, struct = new_seq, new_target
        lines[p.seq_i] = p.seq_prefix + new_seq
        lines[p.struct_i] = p.struct_prefix + new_target

    block = lines[a:b]
    is_label = [bool(_LABEL.match(l)) for l in block]       # e.g. stray "row 1: ..." lines
    width = max((len(l) for l in block), default=0)
    grid = [list(" " * width) if lab else list(l.ljust(width)) for l, lab in zip(block, is_label)]

    path, new_markers = _trace(grid, (template, seq))
    if len(path) != len(seq):
        raise BlueprintError(f"Length mismatch: blueprint has {len(path)} nucleotide cells "
                             f"but the sequence has {len(seq)} nt.")

    n_filled = 0
    for i, (r, c) in enumerate(path):
        code, nt = grid[r][c], seq[i]
        if code in FIXED and not overwrite_all:
            if _norm(code) != nt:
                warnings.append(f"position {i + 1}: blueprint fixes '{code}' but sequence has '{nt}'")
            continue
        if code in IUPAC and nt in "ACGU" and nt not in IUPAC[code]:
            warnings.append(f"position {i + 1}: blueprint code '{code}' does not allow '{nt}'")
        grid[r][c] = nt
        n_filled += 1

    if mark_ends and new_markers:
        if any(c < 0 for _, c in new_markers):               # an end touches the left edge: add a margin
            for row in grid:
                row.insert(0, " ")
            path = [(r, c + 1) for r, c in path]
            new_markers = tuple((r, c + 1) for r, c in new_markers)
        for ch, (r, c) in zip("53", new_markers):
            if 0 <= r < len(grid) and c >= 0:
                if c >= len(grid[r]):                          # just past the right edge: extend the row
                    grid[r].extend(" " * (c + 1 - len(grid[r])))
                if grid[r][c] == " ":
                    grid[r][c] = ch
                    continue
            warnings.append(f"could not write the '{ch}' marker at drawing row {r}, col {c}: no free cell")

    def _row(row, l):
        out = "".join(row).rstrip()
        return out + " " * (len(l) - len(out)) if l.endswith(" ") else out

    new_block = [l if lab else _row(row, l) for row, l, lab in zip(grid, block, is_label)]
    return FillResult(
        lines=lines[:a] + new_block + lines[b:],
        blueprint=new_block,
        sequence=seq,
        structure=struct,
        path=path,
        n_filled=n_filled,
        warnings=warnings,
        design_info=info,
    )


# --------------------------------------------------------------------------- #
# CLI (thin wrapper, handy for testing)
# --------------------------------------------------------------------------- #
def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Fill an origami blueprint with a designed sequence.")
    ap.add_argument("infile", help="origami file")
    ap.add_argument("design", nargs="?", help="optional design output file")
    ap.add_argument("--run", type=int, default=1)
    ap.add_argument("-o", "--outfile")
    ap.add_argument("--blueprint-only", action="store_true")
    ap.add_argument("--overwrite-all", action="store_true")
    ap.add_argument("--no-mark-ends", action="store_true", help="don't write 5/3 markers when the ends were found from the sequence")
    args = ap.parse_args(argv)

    inp = Path(args.infile)
    try:
        res = fill_blueprint(
            inp.read_text(encoding="utf-8"),
            Path(args.design).read_text(encoding="utf-8") if args.design else None,
            run=args.run, overwrite_all=args.overwrite_all,
            mark_ends=not args.no_mark_ends,
        )
    except BlueprintError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    out = Path(args.outfile) if args.outfile else inp.with_name(inp.stem + "_filled" + inp.suffix)
    out.write_text(res.text(args.blueprint_only), encoding="utf-8")
    for w in res.warnings:
        print(f"warning: {w}", file=sys.stderr)
    print(f"{res.n_cells} nucleotide cells traced, {res.n_filled} replaced -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())