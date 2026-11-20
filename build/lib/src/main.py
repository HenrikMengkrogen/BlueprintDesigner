
from __future__ import annotations
import pyfurnace as pf

from curses import window
import math, sys
from dataclasses import dataclass
from pathlib import Path
import os
import platform
import shutil
import subprocess
import sys

from numpy import random
from .fill_blueprint import *



from PySide6.QtWidgets import QTabWidget
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView



from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetricsF, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFormLayout,
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem,
    QGraphicsView, QLabel, QLineEdit, QListWidget, QMainWindow, QPlainTextEdit,
    QSpinBox, QSplitter, QVBoxLayout, QWidget)
from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QGraphicsItem
from PySide6.QtCore import QMimeData, Qt, Signal, QPointF, QRectF, QLineF
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsSimpleTextItem, QGraphicsView, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QMimeData, Qt, Signal, QPointF, QRectF, QLineF, QEvent
import json
from PySide6.QtGui import QCursor   

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsSimpleTextItem, QGraphicsView, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)

from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout,
    QGraphicsItem, QGraphicsRectItem, QGraphicsScene,
    QGraphicsSimpleTextItem, QGraphicsView, QInputDialog, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMessageBox, QPlainTextEdit,
    QSpinBox, QSplitter, QVBoxLayout, QWidget,
)



import os, shutil, sys, tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLineEdit,
                               QSpinBox, QDoubleSpinBox, QLabel, QVBoxLayout)

from PySide6.QtCore import QUrl
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtCore import QProcessEnvironment

#from rope.tools import *

CPUS = os.cpu_count() or 1




DRAG_THRESHOLD = 5
SNAP_DIST = 10   # px
BOX_COLS = 15   # width in monospace character cells
BOX_ROWS = 7    # height in text lines
DECORATIVE_MOTIFS = {
    "vertical_link",
    "vertical_double_link",
}

MIN_ZOOM, MAX_ZOOM = 0.2, 5.0
CLIP_MARKER = "blueprint-designer-motifs"   




@dataclass
class Param:
    name: str
    kind: str                 
    default: object
    lo: int = 0
    hi: int = 100
    choices: tuple = ()
    tip: str = ""

NONE = []
OPEN_LEFT = Param("open_left", "bool", False, tip="Flip so the loop opens to the left")
SEQ = Param("sequence", "str", "", tip="5'->3'. Empty = unspecified (N)")
KL = [OPEN_LEFT, SEQ,
      Param("pk_index", "str", "0",
            tip="Kissing partners share an index: '1' pairs with \"1'\"")]
KD =  [SEQ, Param("pk_index", "str", "0",
            tip="Kissing partners share an index: '1' pairs with \"1'\""), 
            Param("Energy", "float", "-8.5")]

START_END_STEM = [
        Param("up_left", "str", "3", tip = "position of the 3' end"),
        Param("up_right", "str", "5", tip = "position of the 5' end"),
        Param("down_left", "str", "-"),
        Param("down_right", "str", "-"),
    ]

SINGLE_STRAND = [
    Param("sequence", "str", "", tip="Top strand, 5'->3'. Empty = unspecified"),
    Param("loop", "bool", False, tip="If True, the single-stranded region forms a loop. Default is False.")
]

SPECS = {
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
    "BranchedKissingLoop" : KL,
    "KissingDimer" : KD,
    "AlphaKissingLoop": KL,
    "Ispinach" : NONE,
    "Mango" : [OPEN_LEFT],
    "MalachiteGreen" : [OPEN_LEFT],
    "MalachiteGreenShort" : NONE,
    "Broccoli" : NONE,
    "OrangeBroccoli" : NONE,
    "RedBroccoli" : NONE,
    "Pepper" : NONE,
    "Biotin" :  NONE,
    "PIP3" :  [OPEN_LEFT],
    "PIP3_mut1" : [OPEN_LEFT],
    "PIP3_mut3" : [OPEN_LEFT],
    "PIP3_mut5" : [OPEN_LEFT],
    "MS2" : [OPEN_LEFT],
    "PP7" : [OPEN_LEFT],
    "TAR_TAT" : [OPEN_LEFT],
    "L7Ae" : NONE,
    "Streptavidin" : [OPEN_LEFT],
    "Thrombin_exosite1" : [OPEN_LEFT],
    "Thrombin_exosite2" : [OPEN_LEFT],
    "LambdaTurn" : NONE,
    "ThreeWayJunction" : NONE,
    "Bend90" : NONE,
    "KissingDimer120" : KD,
    "BranchedDimer" : KD,
    "AlphaKissingDimer" : KD,
    "start_end_stem" : START_END_STEM,
    "single_strand" : SINGLE_STRAND,
    "vertical_link" : NONE,
    "vertical_double_link" : NONE,
}

# which parameter a right-edge drag changes (1 character = 1 bp)
RESIZE_PARAM = {"Stem": "length", "Dovetail": "length"}

# only offer classes this pyFuRNAce version actually exports
AVAILABLE = [n for n in SPECS if hasattr(pf, n)]
print("Skipped (not found in pf):", [n for n in SPECS if n not in AVAILABLE])

COLORS = {"Stem": "#9ecae1", "Dovetail": "#dadaeb", "Loop": "#c7e9c0",
          "TetraLoop": "#c7e9c0", "KissingLoop120": "#fdae6b",
          "KissingLoop180": "#fdae6b", "BranchedKissingLoop": "#f35a43",
          "KissingDimer": "#a0e725", "AlphaKissingLoop" : "#255fe7", "Ispinach" : "#25e728",
          "Mango" : "#e7c725", "MalachiteGreen" : "#00bc03", "MalachiteGreenShort" : "#25e728",
          "Broccoli" : "#039e05", "OrangeBroccoli" : "#dfb10a", "RedBroccoli" : "#e72525", "Pepper" : "#a40c07",
          "Biotin" : "#b9aeff", "PIP3" : "#25e728", "PIP3_mut1" : "#25e728", "PIP3_mut3" : "#25e728",
          "PIP3_mut5" : "#25e728", "MS2" : "#82ffdaff", "PP7" : "#689339", "TAR_TAT" : "#2b9274", "L7Ae" : "#f9baff",
          "Streptavidin" : "#e725b3", "Thrombin_exosite1" : "#F7C0FF", "Thrombin_exosite2" : "#b172f8ff",
          "LambdaTurn" : "#e725b3", "ThreeWayJunction" : "#e725b3", "Bend90" : "#e725b3", "KissingDimer120" : "#e725b3",
          "BranchedDimer" : "#e725b3", "AlphaKissingDimer" : "#fa46ca", "start_end_stem" : "#e725b3", "single_strand" : "#e725b3",
          "vertical_link" : "#e725b3", "vertical_double_link" : "#e725b3"}


import random
from .fill_blueprint import IUPAC     # IUPAC isn't in __all__, so import it explicitly

_PAIRS = [("A", "U"), ("U", "A"), ("G", "C"), ("C", "G"), ("G", "U"), ("U", "G")]
_OPEN, _CLOSE = "([{<", ")]}>"


def _allowed(code):
    if code in "ACGU":
        return set(code)
    return set(IUPAC.get(code, "ACGU"))



def randomize_blueprint(text, rng=random):
    """Replace every ambiguous letter (N, K, S, ...) with a random nucleotide.

    Paired positions get complementary bases (incl. G-U wobble), so stems stay valid.
    Fixed A/C/G/U letters are kept.
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
    return fill_blueprint(text, design).text()

def build_kwargs(cls_name, values):
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


def mono_font():
    f = QFont("Menlo")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setFixedPitch(True)
    f.setPointSize(11) #11
    return f

def cell_size():
    """
    Pixel dimensions of one monospaced text cell.

    lineSpacing(), not boundingRect().height(), is the distance between
    consecutive rendered text lines.
    """
    fm = QFontMetricsF(mono_font())

    return (
        fm.horizontalAdvance("M"),
        fm.lineSpacing(),
    )
def application_dir():
    """
    Return the application/project root.
    """
    if "__file__" in globals():
       
        return Path(__file__).resolve().parent.parent

    return Path.cwd().resolve()


def ensure_executable(path):
    """
    Confirm that the bundled AROS binary exists and is executable.
    """
    path = Path(path)

    if not path.is_file():
        raise FileNotFoundError(
            f"AROS executable not found:\n{path}\n\n"
            "Check that the appropriate binary is present in the bin folder."
        )

    if os.name != "nt":
        path.chmod(path.stat().st_mode | 0o111)

    return path

APP_DIR = application_dir()

def aros_binary_path():
    """
    Return the AROS executable bundled for the current platform.
    """
    system = platform.system()

    if system == "Darwin":
        return APP_DIR / "bin" / "aros-macos"

    if system == "Linux":
        return APP_DIR / "bin" / "aros-linux"

    if system == "Windows":
        return APP_DIR / "bin" / "aros-windows.exe"

    raise RuntimeError(f"Unsupported operating system: {system}")


AROS_BIN = aros_binary_path()

# These must match the paths hard-coded or configured inside AROS.
AROS_INPUT_FILE = APP_DIR / "misc" / "input_1.txt"
AROS_OUTPUT_DIR = APP_DIR / "misc" / "output"


def xy(p):
    try:
        return int(p[0]), int(p[1])
    except Exception:
        return int(p.x), int(p.y)


def junction_edges(motif):
    """
    Return motif junction locations grouped by edge.

    Keys:
        L = left
        R = right
        T = top
        B = bottom

    Returns None when the motif does not expose usable junction data.
    """
    try:
        out = {"L": [], "R": [], "T": [], "B": []}

        for direction, positions in motif.junctions.items():
            dx, dy = xy(direction)

            if dx > 0 and dy == 0:
                edge = "R"
            elif dx < 0 and dy == 0:
                edge = "L"
            elif dx == 0 and dy < 0:
                edge = "T"
            elif dx == 0 and dy > 0:
                edge = "B"
            else:
                # Ignore diagonal or zero-vector junction directions.
                continue

            out[edge] = sorted(xy(position) for position in positions)

        return out

    except Exception:
        return None

def horizontal_anchor_row(motif):
    """
    Return the central row of the motif's left/right junctions.

    The result is in motif text-grid row coordinates.
    """
    edges = junction_edges(motif)

    if not edges:
        return None

    rows = []

    for edge in ("L", "R"):
        for _, y in edges[edge]:
            rows.append(y)

    if not rows:
        return None

    return (min(rows) + max(rows)) / 2



def junction_rows(motif):
    """{'L': [rows], 'R': [rows]} of left/right junctions (top->bottom), or None."""
    try:
        out = {"L": [], "R": []}
        for d, positions in motif.junctions.items():
            dx, dy = xy(d)
            if dy == 0 and dx != 0:
                out["R" if dx > 0 else "L"] = sorted(xy(p)[1] for p in positions)
        return out
    except Exception:
        return None

def rows_overlap(a, b):
    return not (a.bottom() <= b.top() or a.top() >= b.bottom())

def motif_row_span(cls_name):
    """
    Number of blueprint rows occupied by this motif.
    """
    if cls_name == "AlphaKissingLoop":
        return 2

    return 1

def write_aros_input(sequence, structure, path):
    """
    Write the exact input format consumed by AROS.

    AROS requires equal-length sequence and dot-bracket structure strings.
    """
    sequence = "".join(sequence.split())
    structure = "".join(structure.split())

    if len(sequence) != len(structure):
        raise ValueError(
            f"Sequence and structure must have the same length: "
            f"{len(sequence)} != {len(structure)}"
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"Sequence:{sequence}\n"
        f"Structure:{structure}\n",
        encoding="utf-8",
    )

    return path


def read_aros_outputs(output_dir=AROS_OUTPUT_DIR):
    """
    Read all AROS result files below misc/output/run_*/.
    """
    output_dir = Path(output_dir)

    if not output_dir.is_dir():
        raise FileNotFoundError(
            f"AROS output directory does not exist:\n{output_dir}"
        )

    # Supports output_1.txt, outpu_1.txt, or any other .txt output name.
    files = sorted(
        path
        for path in output_dir.rglob("*.txt")
        if path.is_file()
    )

    if not files:
        raise FileNotFoundError(
            f"No AROS .txt output files were found below:\n{output_dir}"
        )

    candidates = []

    for output_path in files:
        sequence = None
        target_structure = None
        mfe_structure = None
        bp_distance = float("inf")
        ensemble_diversity = float("inf")
        mfe = None

        for raw_line in output_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines():
            line = raw_line.strip()

            # Ignore headings such as: ==== FINAL (run 1) ====
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "sequence":
                sequence = "".join(value.split()).upper()

            elif key == "target":
                # This is the desired dot-bracket structure.
                target_structure = "".join(value.split())

            elif key == "mfe structure":
                # This is the structure folded from the designed sequence.
                mfe_structure = "".join(value.split())

            elif key == "bp_distance":
                try:
                    bp_distance = int(value)
                except ValueError:
                    pass

            elif key == "mfe":
                try:
                    mfe = float(value)
                except ValueError:
                    pass

            elif key == "ensemble diversity":
                try:
                    ensemble_diversity = float(value)
                except ValueError:
                    pass

        if sequence is None or target_structure is None:
            print(f"Skipping incomplete AROS output: {output_path}")
            continue

        if len(sequence) != len(target_structure):
            print(
                f"Skipping malformed AROS output: {output_path}\n"
                f"  sequence length: {len(sequence)}\n"
                f"  target length:   {len(target_structure)}"
            )
            continue

        candidates.append({
            "path": output_path,
            "filename": str(output_path.relative_to(output_dir)),
            "sequence": sequence,
            "structure": target_structure,
            "mfe_structure": mfe_structure,
            "bp_distance": bp_distance,
            "mfe": mfe,
            "ensemble_diversity": ensemble_diversity,
        })

    if not candidates:
        raise ValueError(
            "AROS created output files, but none matched the expected "
            "AROS result format."
        )

   
    return sorted(
        candidates,
        key=lambda candidate: (
            candidate["bp_distance"],
            candidate["ensemble_diversity"],
            candidate["filename"],
        ),
    )



CPUS = os.cpu_count() or 1

@dataclass
class Opt:
    flag: str            
    label: str
    kind: str           
    default: object
    tip: str = ""

@dataclass
class Tool:
    exe: str
    title: str
    opts: list[Opt] = field(default_factory=list)
    needs_input: bool = True      

RUNS = Opt("-r", "Runs", "int", 3)
WORKERS = Opt("-w", "Workers/threads", "int", min(4, CPUS))

TOOLS = {t.exe: t for t in [
    Tool("rope-fold",     "Predict sequences (batch)", [RUNS, WORKERS]),
    Tool("rope-dragon",   "Predict sequences (continuous)",
         [RUNS, WORKERS, Opt("-e", "Ensemble diversity (ED)", "float", 0.0),
          Opt("-t", "Time per run", "float", 60.0)]),
    Tool("rope-build",    "Build PDB files",
         [Opt("--ligand", "Ligand (MODULE=LIGAND)", "str", "")]),
    Tool("rope-flip",     "Flip blueprint")
]}


def find_exe(name: str) -> str:
    """PATH first, then the scripts folder of the running interpreter."""
    found = shutil.which(name)
    if found:
        return found
    for cand in (Path(sys.executable).parent / name,
                 Path(sys.executable).parent / f"{name}.exe",
                 Path(sys.executable).parent / "Scripts" / f"{name}.exe"):
        if cand.exists():
            return str(cand)
    raise FileNotFoundError(f"{name} not found. Is the package installed in this environment?")


class OptionsDialog(QDialog):
    def __init__(self, tool: Tool, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tool.title)
        self.tool, self.widgets = tool, {}
        lay = QVBoxLayout(self)
        form = QFormLayout()
        for o in tool.opts:
            if o.kind == "int":
                w = QSpinBox(); w.setRange(1, 100000); w.setValue(o.default)
            elif o.kind == "float":
                w = QDoubleSpinBox(); w.setRange(0, 1e6); w.setValue(o.default)
            else:
                w = QLineEdit(str(o.default))
            w.setToolTip(o.tip)
            self.widgets[o.flag] = w
            form.addRow(o.label, w)
        lay.addLayout(form)
        if not tool.opts:
            lay.addWidget(QLabel("No options. Run with current blueprint."))
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def args(self) -> list[str]:
        out = []
        for o in self.tool.opts:
            w = self.widgets[o.flag]
            v = w.text().strip() if isinstance(w, QLineEdit) else w.value()
            if v == "" :
                continue
            out += [o.flag, str(v)]
        return out


class RopeRunner(QObject):
    output = Signal(str)          
    finished = Signal(int, str)   
    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc: QProcess | None = None
        self.workdir = ""
        self.base_dir: Path | None = None
        self.current_exe = ""

    def running(self):
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def run(self, tool: Tool, args: list[str], blueprint_text: str | None):
        if self.running():
            self.output.emit("A job is already running. Stop it first.\n")
            return
        try:
            exe = find_exe(tool.exe)
        except FileNotFoundError as ex:
            self.output.emit(f"{ex}\n")
            return

        
        if self.base_dir is None:
            self.base_dir = Path(tempfile.gettempdir())      # fallback
        self.workdir = tempfile.mkdtemp(prefix=f"{tool.exe}_", dir=self.base_dir)
        self.current_exe = tool.exe
        cmd_args = list(args)
        if tool.needs_input:
            bp = Path(self.workdir) / "blueprint.txt"
            bp.write_text(blueprint_text or "", encoding="utf-8")
            cmd_args.append(bp.name)

        self.proc = QProcess(self)                      
        self.proc.setWorkingDirectory(self.workdir)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)

        env = QProcessEnvironment.systemEnvironment()   
        env.insert("PYTHONUNBUFFERED", "1")
        self.proc.setProcessEnvironment(env)

        self.proc.readyReadStandardOutput.connect(
            lambda: self.output.emit(
                bytes(self.proc.readAllStandardOutput()).decode(errors="replace")))
        self.proc.errorOccurred.connect(
            lambda e: self.output.emit(f"\n[process error: {e}]\n"))
        self.proc.finished.connect(
            lambda code, _s: self.finished.emit(code, self.workdir))
        self.output.emit(f"$ {tool.exe} {' '.join(cmd_args)}\n(in {self.workdir})\n\n")
        self.proc.start(exe, cmd_args)   

    def stop(self):
        if self.running():
            self.proc.terminate()
            if not self.proc.waitForFinished(2000):
                self.proc.kill()



class MotifItem(QGraphicsRectItem):
    def __init__(self, cls_name):
        super().__init__()
        self.cls_name = cls_name
        self.params = SPECS[cls_name]
        self.values = {p.name: p.default for p in self.params}
        self.rot, self.flipped, self.motif = 0, False, None
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPen(QPen(QColor("#555"), 0))
        self.setBrush(QBrush(QColor(COLORS.get(cls_name, "#ddd"))))
        self.label = QGraphicsSimpleTextItem(self)
        self.label.setFont(mono_font())
        self.label.setBrush(QBrush(QColor("black")))
        self.row_span = motif_row_span(cls_name)

        
        
        self.natural_width = 0
        self.natural_height = 0
        self.anchor_row = None

        self.resize_margin = 8      # px grab zone on the right edge
        self.resizing = False
        self.resize_x0 = 0
        self.resize_len0 = 0
        self.setAcceptHoverEvents(True)
                




        self.rebuild()

    def is_decorative(self):
        """
        Decorative motifs are drawn using pyFuRNAce, but do not belong to the
        assembled RNA/Origami model.
        """
        return self.cls_name in DECORATIVE_MOTIFS


    def occupies_layout(self):
        """
        True only if this motif contributes RNA sequence/structure and occupies
        a logical blueprint position.
        """
        return not self.is_decorative()


    def lane_y(self):
        """Scene y of the top-most horizontal junction = this motif's row."""
        _, ch = cell_size()
        edges = junction_edges(self.motif) or {}
        ys = [y for e in ("L", "R") for _, y in edges.get(e, [])]
        if not ys:
            return self.srect().center().y()
        top = self.label.boundingRect().top()
        return self.label.mapToScene(QPointF(0, top + (min(ys) + 0.5) * ch)).y()

    def junction_scene_pos(self, junction):
        """
        Return the center of a junction cell in scene coordinates.

        This deliberately maps through self.label, so it stays correct even if
        the label receives a local offset later.
        """
        col, row = xy(junction)
        cw, ch = cell_size()

        # QGraphicsSimpleTextItem may have a small font-dependent top/left
        # bounding offset. Include it instead of assuming text begins at (0, 0).
        text_rect = self.label.boundingRect()

        local_point = QPointF(
            text_rect.left() + (col + 0.5) * cw,
            text_rect.top() + (row + 0.5) * ch,
        )

        return self.label.mapToScene(local_point)

   
        # --- mouse: drag right edge to resize, otherwise move + snap ---
    def can_resize(self):
        return (self.cls_name in RESIZE_PARAM
                and self.rot % 2 == 0                 # not rotated
                and not self.values.get("sequence"))  # a sequence fixes the length

    def _on_resize_edge(self, pos):
        return self.can_resize() and abs(pos.x() - self.rect().right()) <= self.resize_margin

    def hoverMoveEvent(self, e):
        if self._on_resize_edge(e.pos()):
            self.setCursor(Qt.CursorShape.SizeHorCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(e)

    def hoverLeaveEvent(self, e):
        self.unsetCursor()
        super().hoverLeaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._on_resize_edge(e.pos()):
            self.resizing = True
            self.resize_x0 = e.scenePos().x()
            self.resize_len0 = self.values[RESIZE_PARAM[self.cls_name]]
            self.setSelected(True)
            e.accept()
            return
        self._press_pos = e.scenePos()
        self._dragging = False

        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.resizing:
            key = RESIZE_PARAM[self.cls_name]
            p = next(p for p in self.params if p.name == key)
            cw, _ = cell_size()
            sign = -1 if self.resize_len0 < 0 else 1          # dovetail direction
            n = abs(self.resize_len0) + round((e.scenePos().x() - self.resize_x0) / cw)
            n = max(1, min(max(abs(p.lo), abs(p.hi)), n))
            if sign * n != self.values[key]:
                self.set_state(values={**self.values, key: sign * n})  # pushes neighbours
            e.accept()
            return
        if not self.resizing and not getattr(self, "_dragging", False):
            delta = e.scenePos() - self._press_pos
            if abs(delta.x()) + abs(delta.y()) < DRAG_THRESHOLD:
                e.accept()
                return
            self._dragging = True
        super().mouseMoveEvent(e)
        ghost, t = self.scene().ghost, self.find_snap()
        if t is not None:
            ghost.setRect(t.x(), t.y(), self.rect().width(), self.rect().height())
            #ghost.setRect(t.x(), t.y(), self.rect().width(), self.rect().height())
            ghost.show()
        else:
            ghost.hide()

    def mouseReleaseEvent(self, e):
        if self.resizing:
            self.resizing = False
            view = self.scene().views()[0]
            view.normalize_box_heights()
            view.motif_edited.emit(self)     # refresh the properties form
            e.accept()
            return
        super().mouseReleaseEvent(e)
        self.scene().ghost.hide()
        self.snap()



    


    



    # --- model ---
    def rebuild(self):
        """Construct the motif first; only commit if nothing raised."""
        m = getattr(pf, self.cls_name)(**build_kwargs(self.cls_name, self.values))
        if self.rot:
            r = m.rotate(self.rot); m = r if r is not None else m
        if self.flipped:
            r = m.flip(horizontally=True, vertically=False); m = r if r is not None else m
        try:
            text = str(m).rstrip("\n")
        except Exception:
            text = self.cls_name
        self.motif = m
        self.anchor_row = horizontal_anchor_row(self.motif)
        lines = text.splitlines() or [""]

        cw, ch = cell_size()

        self.label.setText(text)
        self.label.setPos(0, 0)

        self.natural_width = max(len(line) for line in lines) * cw
        self.natural_height = len(lines) * ch
        self.setRect(0, 0, self.natural_width, self.natural_height)





    def set_state(self, values=None, rot=None, flipped=None):
        """Apply a change; returns an error string (and reverts) on failure."""
        prev = (self.values, self.rot, self.flipped)
        if values is not None: self.values = values
        if rot is not None: self.rot = rot
        if flipped is not None: self.flipped = flipped
        old = self.srect()
        try:
            self.rebuild()
        except Exception as ex:
            self.values, self.rot, self.flipped = prev
            return f"{type(ex).__name__}: {ex}"
        new = self.srect()

        dx = new.width() - old.width()
        dy = new.height() - old.height()

        if abs(dx) > 0.5:
            self.push_neighbours_right(old.right(), dx)

        if abs(dy) > 0.5:
            self.push_neighbours_down(old.bottom(), dy)

        return None

    # --- geometry ---
    def srect(self):
        return self.mapRectToScene(self.rect())

    def other_items(self):
        if not self.scene():
            return []
        return [i for i in self.scene().items()
                if isinstance(i, MotifItem) and i is not self]

    def push_neighbours_right(self, old_right, dx):
        """Move attached RNA motifs horizontally by dx."""
        if not self.occupies_layout():
            return

        me = self.srect()

        for other in self.other_items():
            if not other.occupies_layout():
                continue

            r = other.srect()

            if abs(r.left() - old_right) < 1 and rows_overlap(me, r):
                other_right = r.right()
                other.moveBy(dx, 0)
                other.push_neighbours_right(other_right, dx)


    def push_neighbours_down(self, old_bottom, dy):
        """Move attached RNA motifs vertically by dy."""
        if not self.occupies_layout():
            return

        me = self.srect()

        for other in self.other_items():
            if not other.occupies_layout():
                continue

            r = other.srect()

            horizontal_overlap = not (
                r.right() <= me.left()
                or r.left() >= me.right()
            )

            if abs(r.top() - old_bottom) < 1 and horizontal_overlap:
                other_bottom = r.bottom()
                other.moveBy(0, dy)
                other.push_neighbours_down(other_bottom, dy)

   


 
    def find_snap(self):
        """
        Closest compatible junction pair, horizontal or vertical.

        Left/right pairs: boxes butt edge to edge, junction rows are aligned.
        Top/bottom pairs: boxes butt top to bottom, junction columns are aligned.
        Returns the new scene position of this item, or None.
        """
        if self.motif is None or self.scene() is None:
            return None
        mine = junction_edges(self.motif)
        if not mine:
            return None

        me = self.srect()
        others = [
                item
                for item in self.scene().items()
                if (
                    isinstance(item, MotifItem)
                    and item is not self
                    and item.motif is not None
                    and item.occupies_layout()
                )
            ]


        best, best_d = None, float("inf")
        for other in others:
            theirs = junction_edges(other.motif)
            if not theirs:
                continue
            r = other.srect()

            # (my edge, their edge, axis, new left, new top)
            configs = [
                ("L", "R", "h", r.right(),                None),                 
                ("R", "L", "h", r.left() - me.width(),    None),                
                ("T", "B", "v", None,                     r.bottom()),           
                ("B", "T", "v", None,                     r.top() - me.height()) 
            ]
            for my_edge, their_edge, axis, new_left, new_top in configs:
                for mp in mine[my_edge]:
                    my_pos = self.junction_scene_pos(mp)
                    for tp in theirs[their_edge]:
                        their_pos = other.junction_scene_pos(tp)
                        if axis == "h":
                            dx = new_left - me.left()
                            dy = their_pos.y() - my_pos.y()
                        else:
                            dx = their_pos.x() - my_pos.x()
                            dy = new_top - me.top()
                        d = abs(dx) + abs(dy)
                        if d >= SNAP_DIST or d >= best_d:
                            continue
                        target = me.translated(dx, dy)
                        if (
                            self.occupies_layout()
                            and any(
                                target.adjusted(1, 1, -1, -1).intersects(other.srect())
                                for other in others
                            )
                        ):
                            continue         # that slot is already occupied
                        best, best_d = QPointF(self.x() + dx, self.y() + dy), d
        return best
   

   

    def snap(self):
        target = self.find_snap()

        if target is not None:
            self.setPos(target)
            return

        cw, ch = cell_size()

        self.setPos(
            round(self.x() / cw) * cw,
            round(self.y() / ch) * ch,
        )




VIEWER_HTML = """<html><body style="margin:0;overflow:hidden;background:white">
<div id="v" style="width:100vw;height:100vh;position:relative"></div>
<div id="msg" style="position:absolute;top:4px;left:4px;color:red;font:12px monospace"></div>
<script src="__SRC__"></script>
<script>
try {
  const pdb = __PDB__;
  const v = $3Dmol.createViewer("v", {backgroundColor: "white"});
  v.addModel(pdb, "pdb");
  v.setStyle({}, {stick: {radius: 0.2}});
  v.setStyle({}, {stick: {radius: 0.2}, cartoon: {color: "spectrum"}});
  v.zoomTo(); v.render();
  window.addEventListener("resize", () => { v.resize(); v.render(); });
} catch (e) {
  document.getElementById("msg").textContent = "Viewer error: " + e;
  console.log("Viewer error: " + e);
}
</script></body></html>"""


class LoggingPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, msg, line, src):
        print(f"[JS] {msg}  ({src}:{line})")


class StructureViewer(QWidget):
    """Lists the .pdb files in a folder and shows the selected one in 3D."""
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self.combo = QComboBox()
        self.web = QWebEngineView()
        self.web.setPage(LoggingPage(self.web))
        s = self.web.settings()
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        s.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        lay.addWidget(self.combo)
        lay.addWidget(self.web, 1)
        self.files = []
        self.tmpdir = Path(tempfile.mkdtemp(prefix="viewer_"))
        self.combo.currentIndexChanged.connect(self.show_current)

    def load_folder(self, folder):
        folder = Path(folder)
        self.files = sorted(folder.rglob("*.pdb"))
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems([str(p.relative_to(folder)) for p in self.files])
        self.combo.blockSignals(False)
        if self.files:
            self.show_current(0)
        return len(self.files)

    def show_current(self, i):
        if not (0 <= i < len(self.files)):
            return
        pdb = self.files[i].read_text(errors="replace")
        local = APP_DIR / "misc" / "3Dmol-min.js"
        src = local.as_uri() if local.exists() else "https://3Dmol.org/build/3Dmol-min.js"
        html = (VIEWER_HTML.replace("__SRC__", src)
                           .replace("__PDB__", json.dumps(pdb)))
        page = self.tmpdir / "viewer.html"
        page.write_text(html, encoding="utf-8")
        self.web.load(QUrl.fromLocalFile(str(page)))
        print(f"[viewer] {self.files[i]}  ({len(pdb)} chars, script: {src})")

    def showEvent(self, e):
        super().showEvent(e)
        if self.files:                      
            self.show_current(self.combo.currentIndex())

class PropertiesPanel(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self.title = QLabel("Select a motif to edit it")
        self.title.setStyleSheet("font-weight: bold")
        self.host = QWidget()
        self.cls_name = None
        self.templates = {}
        self.form = QFormLayout(self.host)
        self.error = QLabel()
        self.error.setStyleSheet("color: #d62728")
        self.error.setWordWrap(True)
        self.info = QPlainTextEdit()
        self.info.setReadOnly(True)
        self.info.setFont(mono_font())
        for w in (self.title, self.host, self.error):
            lay.addWidget(w)
        #lay.addWidget(self.info, 1)

        self.viewer = StructureViewer()
        self.tabs = QTabWidget()
        self.tabs.addTab(self.info, "Info")
        self.tabs.addTab(self.viewer, "3D")
        lay.addWidget(self.tabs, 1)
        self.item, self.widgets = None, {}

    def _clear_form(self):
        self.item = None
        self.cls_name = None
        while self.form.rowCount():
            self.form.removeRow(0)
        self.widgets = {}
        self.error.clear()

    def show_class(self, cls_name):
        self._clear_form()
        self.title.setText(f"{cls_name} (template for new motifs)")
        vals = self.templates.setdefault(
            cls_name, {p.name: p.default for p in SPECS[cls_name]}
        )
        for p in SPECS[cls_name]:
            w = self._make(p, vals[p.name])
            self.widgets[p.name] = w
            self.form.addRow(p.name, w)
        self.cls_name = cls_name
        self.update_info()

    def update_preview(self):
        name = self.cls_name
        try:
            m = getattr(pf, name)(**build_kwargs(name, {n: self._read(w) for n, w in self.widgets.items()}))
            self.info.setPlainText(f"{m}\n\nsequence:  {m.sequence}\nstructure: {m.structure}")
        except Exception as ex:
            self.error.setText(f"{type(ex).__name__}: {ex}")

    def show_item(self, item):
        self._clear_form()
        if item is None:
            self.title.setText("Select a motif to edit it")
            self.info.clear()
            return
        self.title.setText(item.cls_name)
        for p in item.params:
            w = self._make(p, item.values[p.name])
            self.widgets[p.name] = w
            self.form.addRow(p.name, w)
        self.item = item
        self.update_info()

    def _make(self, p, val):
        if p.kind == "int":
            w = QSpinBox(); w.setRange(p.lo, p.hi); w.setValue(val)
            w.valueChanged.connect(self.on_change)
        elif p.kind == "bool":
            w = QCheckBox(); w.setChecked(val)
            w.toggled.connect(self.on_change)
        elif p.kind == "choice":
            w = QComboBox(); w.addItems(p.choices); w.setCurrentText(val)
            w.currentTextChanged.connect(self.on_change)
        else:
            w = QLineEdit(val)
            w.editingFinished.connect(self.on_change)
        w.setToolTip(p.tip)
        return w

    @staticmethod
    def _read(w):
        if isinstance(w, QSpinBox): return w.value()
        if isinstance(w, QCheckBox): return w.isChecked()
        if isinstance(w, QComboBox): return w.currentText()
        return w.text().strip()

    def on_change(self, *_):
        values = {n: self._read(w) for n, w in self.widgets.items()}
        if self.item:                              
            if values == self.item.values:
                return
            self.error.setText(self.item.set_state(values=values) or "")
            self.update_info()
        elif self.cls_name:                       
            self.templates[self.cls_name] = values
            self.update_preview()



    def update_info(self):
        try:
            m = self.item.motif
            self.info.setPlainText(f"{m}\n\nsequence:  {m.sequence}\nstructure: {m.structure}")
        except Exception as ex:
            self.info.setPlainText(str(ex))


class Palette(QListWidget):
    def __init__(self):
        super().__init__()
        self.addItems(AVAILABLE)
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)

    def mimeData(self, items):
        m = QMimeData()
        m.setText(items[0].text())
        return m



class Canvas(QGraphicsView):
    exported = Signal(str)
    motif_edited = Signal(object)
    saved = Signal(str)

    def __init__(self):
        super().__init__()

        # Safe defaults used before any motif is placed on the canvas.
        _, ch = cell_size()
        self.shared_box_height = ch
        self.connection_lane_y = ch / 2

        scene = QGraphicsScene(self)
        scene.setSceneRect(-3000, -3000, 6000, 6000)

        ghost = QGraphicsRectItem()
        ghost.setPen(QPen(QColor("#2ca02c"), 2, Qt.PenStyle.DashLine))
        ghost.setZValue(-1)
        ghost.hide()

        scene.addItem(ghost)
        scene.ghost = ghost

        self.setScene(scene)
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def dragEnterEvent(self, e): e.acceptProposedAction()
    def dragMoveEvent(self, e):  e.acceptProposedAction()

    


    _paste_count = 0
    _copy_origin = (0.0, 0.0)

    def blueprint_text(self):
        """Blueprint as the rope-* tools expect it: drawing with 5'/3' markers."""
        self.origami()                      # raises if nothing RNA-bearing / can't assemble
        text = self.export()
        try:
            res = fill_blueprint(text)      # no design -> only adds the 5'/3' markers
        except BlueprintError as ex:
            raise ValueError(f"Could not mark the 5'/3' ends: {ex}")
        return ">Origami\n\n" + res.text()

    def copy_selection(self):
        items = self.selected()
        if not items:
            return False
        x0 = min(i.x() for i in items)
        y0 = min(i.y() for i in items)
        data = {
            "marker": CLIP_MARKER,
            "items": [
                {"cls": i.cls_name, "values": i.values, "rot": i.rot,
                "flipped": i.flipped, "dx": i.x() - x0, "dy": i.y() - y0}
                for i in items
            ],
        }
        QApplication.clipboard().setText(json.dumps(data))
        self._copy_origin = (x0, y0)
        self._paste_count = 0
        return True

    def cut_selection(self):
        if self.copy_selection():
            for it in self.selected():
                self.scene().removeItem(it)
            self.normalize_box_heights()

    def paste(self):
        try:
            data = json.loads(QApplication.clipboard().text())
            if data.get("marker") != CLIP_MARKER:
                return
            entries = data["items"]
        except (ValueError, AttributeError, KeyError, TypeError):
            return                      # clipboard holds something else

        cw, ch = cell_size()

        # Paste under the mouse if it's over the canvas, otherwise offset
        # from where the motifs were copied (stepping further on each paste).
        cursor = self.viewport().mapFromGlobal(QCursor.pos())
        if self.viewport().rect().contains(cursor):
            origin = self.mapToScene(cursor)
        else:
            self._paste_count += 1
            n = self._paste_count
            origin = QPointF(self._copy_origin[0] + 2 * cw * n,
                            self._copy_origin[1] + 2 * ch * n)
        ox = round(origin.x() / cw) * cw
        oy = round(origin.y() / ch) * ch

        self.scene().clearSelection()
        errors = []
        for ent in entries:
            cls = ent.get("cls")
            if cls not in SPECS:
                errors.append(f"Unknown motif: {cls}")
                continue
            item = MotifItem(cls)
            err = item.set_state(values=dict(ent["values"]),
                                rot=ent["rot"], flipped=ent["flipped"])
            if err:
                errors.append(f"{cls}: {err}")
                continue
            self.scene().addItem(item)
            item.setPos(ox + ent["dx"], oy + ent["dy"])
            item.setSelected(True)

        self.normalize_box_heights()
        if errors:
            self.exported.emit("\n".join(errors))

    def origami(self):
        """
        Build the pyFuRNAce Origami object from RNA-bearing motifs only.

        vertical_link and vertical_double_link are visual annotations; they are
        intentionally excluded from the assembled RNA sequence and structure.
        """
        rows = self.rows()

        motif_rows = [
            [item.motif for item in row if item.occupies_layout()]
            for row in rows
        ]

        # Remove rows that contained only decorative items.
        motif_rows = [row for row in motif_rows if row]

        if not motif_rows:
            raise ValueError(
                "Nothing RNA-bearing is on the canvas; only decorative links exist."
            )

        return pf.Origami(
            motif_rows,
            align="left",
            copy=True,
        )


    def aros_candidates(self, runs, starts):
        """
        Write the assembled blueprint to AROS input, run the bundled executable and
        return (candidates best-first, AROS stdout). Raises on any failure.
        """
        executable = ensure_executable(AROS_BIN)
 
        sequence, structure = self.aros_input()
        write_aros_input(sequence, structure, path=AROS_INPUT_FILE)
 
        # Answers to AROS's two terminal prompts (complete runs, hill-climbing starts)
        aros_stdin = f"{runs}\n{starts}\n"
        env = {**os.environ, "RUST_BACKTRACE": "1"}
 
        self.clear_aros_outputs()          # only removes old output/run_* folders
 
        result = subprocess.run(
            [str(executable)],
            cwd=APP_DIR,
            input=aros_stdin,
            text=True,
            capture_output=True,
            timeout=1200, # 20 minutes
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"AROS failed with exit code {result.returncode}.\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )
 
        return read_aros_outputs(AROS_OUTPUT_DIR), result.stdout
 
    # ------------------------------------------------------------------ #
    def run_aros(self, runs, starts):
        """Run AROS and return a text report about the best candidate (unchanged output)."""
        candidates, stdout = self.aros_candidates(runs, starts)
        best = candidates[0]
 
        summary = "\n".join(
            f"# {number}. {candidate['filename']}  "
            f"bp_distance={candidate['bp_distance']}, "
            f"Ensemble Diversity={candidate['ensemble_diversity']}"
            for number, candidate in enumerate(candidates, start=1)
        )
        return (
            "# AROS design completed\n"
            f"# Complete runs: {runs}\n"
            f"# Hill-climbing starts per run: {starts}\n"
            f"# Valid candidates: {len(candidates)}\n"
            f"# Selected candidate: {best['filename']}\n"
            f"# Best bp_distance: {best['bp_distance']}\n"
            f"# Best Ensemble Diversity: {best['ensemble_diversity']}\n\n"
            f"Target structure : {best['structure']}\n"
            f"MFE structure    : {best['mfe_structure']}\n"
            "# Candidates, best first:\n"
            f"{summary}\n\n"
            f"Sequence  : {best['sequence']}\n"
            f"Structure : {best['structure']}\n\n"
            "# AROS output:\n"
            f"{stdout}"
        )
 
    # ------------------------------------------------------------------ #
    def save_export_with_seq(self, parent=None):
        """
        Export the current blueprint, design a sequence for it with AROS, write the
        best candidate into the blueprint (drawing + Sequence + Structure lines) and
        save it as a UTF-8 .txt file.
 
        Returns True on success, False if cancelled or anything failed.
        """
        # 1. the blueprint as exported today; fail early if it can't be assembled
        try:
            text = self.export()
            self.aros_input()
        except Exception as ex:
            QMessageBox.critical(parent, "Cannot design a sequence",
                                 f"{type(ex).__name__}: {ex}")
            return False
 
        # 2. ask for the file name BEFORE the (slow) AROS run, so a cancel doesn't waste it
        filename, _ = QFileDialog.getSaveFileName(
            parent,
            "Save blueprint with sequence",
            "blueprint_with_seq.txt",
            "Text files (*.txt);;All files (*)",
        )
        if not filename:
            return False
        if not filename.lower().endswith(".txt"):
            filename += ".txt"
 
        settings = self.get_aros_settings(parent)
        if settings is None:
            return False
        runs, starts = settings
 
        # 3. AROS -> best candidate -> fill the blueprint
        self.exported.emit("Running AROS ...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            candidates, _ = self.aros_candidates(runs, starts)
            best = candidates[0]
 
            # same "sequence :" / "target :" format that AROS writes
            design_text = (f"sequence : {best['sequence']}\n"
                           f"target : {best['structure']}\n")
            result = fill_blueprint(text, design_text)
            
 
        except subprocess.TimeoutExpired:
            message = ("AROS timed out after 600 seconds.\n"
                       "Try fewer complete runs or fewer hill-climbing starts.")
            self.exported.emit(message)
            QMessageBox.warning(parent, "AROS timed out", message)
            return False
        except BlueprintError as ex:
            message = f"AROS finished, but the sequence could not be placed in the blueprint:\n{ex}"
            self.exported.emit(message)
            QMessageBox.critical(parent, "Could not fill blueprint", message)
            return False
        except Exception as ex:
            message = f"AROS generation failed:\n{type(ex).__name__}: {ex}"
            self.exported.emit(message)
            QMessageBox.critical(parent, "AROS generation failed", message)
            return False
        finally:
            QApplication.restoreOverrideCursor()
 
        # 4. save
        try:
            with open(filename, "w", encoding="utf-8", newline="\n") as file:
                file.write(">Origami\n\n")
                file.write(result.text())
        except OSError as ex:
            QMessageBox.critical(parent, "Could not save blueprint",
                                 f"Could not write the file:\n{filename}\n\n{ex}")
            return False
 
        report = (f"Saved blueprint with sequence to:\n{filename}\n\n"
                  f"Selected {best['filename']}  "
                  f"(bp_distance={best['bp_distance']}, "
                  f"Ensemble Diversity={best['ensemble_diversity']})\n")
        if result.warnings:
            report += "\nWarnings:\n" + "\n".join(f"  {w}" for w in result.warnings) + "\n"
        self.exported.emit(f"{report}\n{result.text()}")
        self.saved.emit(str(Path(filename).parent))
        return True


    def aros_input(self):
        """
        Return the current assembled sequence and dot-bracket structure.

        This deliberately uses the Origami object directly instead of parsing
        text from self.export().
        """
        ori = self.origami()

        sequence = "".join(str(ori.sequence).split())
        structure = "".join(str(ori.structure).split())

        if len(sequence) != len(structure):
            raise ValueError(
                "The assembled Origami sequence and structure have different "
                f"lengths: {len(sequence)} != {len(structure)}"
            )

        return sequence, structure

    def clear_aros_outputs(self, output_dir=AROS_OUTPUT_DIR):
        """
        Remove previous AROS run folders so results from old blueprint designs
        are not mixed with the current AROS invocation.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        for path in output_dir.iterdir():
            if path.is_dir() and path.name.startswith("run_"):
                shutil.rmtree(path)

    
    def get_aros_settings(self, parent=None):
        """
        Collect the two values requested interactively by AROS.

        AROS prompts:
            How many complete runs should be performed? [3]:
            How many hill-climbing starts per run? [5]:
        """
        runs, ok = QInputDialog.getInt(
            parent,
            "AROS configuration",
            "Complete runs:",
            3,
            1,
            1000,
            1,
        )

        if not ok:
            return None

        starts, ok = QInputDialog.getInt(
            parent,
            "AROS configuration",
            "Hill-climbing starts per run:",
            5,
            1,
            10000,
            1,
        )

        if not ok:
            return None

        return runs, starts


    def _run_aros(self, runs, starts):
        """
        Write the assembled blueprint to AROS input, run the bundled executable,
        and return the best generated sequence candidate.
        """
        executable = ensure_executable(AROS_BIN)

        sequence, structure = self.aros_input()

        write_aros_input(
            sequence,
            structure,
            path=AROS_INPUT_FILE,
        )

        
        aros_stdin = f"{runs}\n{starts}\n"

        env = {
            **os.environ,
            "RUST_BACKTRACE": "1",
        }

        # Remove only old output/run_* directories before creating new results.
        self.clear_aros_outputs()

        result = subprocess.run(
            [str(executable)],
            cwd=APP_DIR,
            input=aros_stdin,
            text=True,
            capture_output=True,
            timeout=600,
            env=env,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"AROS failed with exit code {result.returncode}.\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )
        all_files = list(AROS_OUTPUT_DIR.rglob("*"))

        print("AROS output directory:", AROS_OUTPUT_DIR)
        print("Files/directories found after AROS:")
        for path in all_files:
            print(" ", path)
        candidates = read_aros_outputs(AROS_OUTPUT_DIR)
        best = candidates[0]

        summary = "\n".join(
            f"# {number}. {candidate['filename']}  "
            f"bp_distance={candidate['bp_distance']}, "
            f"Ensemble Diversity={candidate['ensemble_diversity']}"
            for number, candidate in enumerate(candidates, start=1)
        )


        return (
            "# AROS design completed\n"
            f"# Complete runs: {runs}\n"
            f"# Hill-climbing starts per run: {starts}\n"
            f"# Valid candidates: {len(candidates)}\n"
            f"# Selected candidate: {best['filename']}\n"
            f"# Best bp_distance: {best['bp_distance']}\n"
            f"# Best Ensemble Diversity: {best['ensemble_diversity']}\n\n"
            f"Target structure: {best['structure']}\n"
            f"MFE structure: {best['mfe_structure']}\n"
            "# Candidates, best first:\n"
            f"{summary}\n\n"
            f"Sequence: {best['sequence']}\n"
            f"Structure: {best['structure']}\n\n"
            "# AROS output:\n"
            f"{result.stdout}"
        )

    def generate_with_aros(self, parent=None):
        """
        Ask for AROS run settings, execute AROS, and show the best result.
        """
        settings = self.get_aros_settings(parent)

        if settings is None:
            return

        runs, starts = settings

        try:
            result_text = self.run_aros(runs, starts)
            self.exported.emit(result_text)

        except subprocess.TimeoutExpired:
            message = (
                "AROS timed out after 600 seconds.\n"
                "Try fewer complete runs or fewer hill-climbing starts."
            )
            self.exported.emit(message)

            if parent is not None:
                QMessageBox.warning(parent, "AROS timed out", message)

        except Exception as ex:
            message = f"AROS generation failed:\n{type(ex).__name__}: {ex}"
            self.exported.emit(message)

            if parent is not None:
                QMessageBox.critical(parent, "AROS generation failed", message)



    

    def save_export(self, parent=None):
        """
        Export the current blueprint and save it as a UTF-8 .txt file.

        Returns True on success, False if cancelled or saving failed.
        """
        text = self.export()

        filename, _ = QFileDialog.getSaveFileName(
            parent,
            "Save blueprint",
            "blueprint.txt",
            "Text files (*.txt);;All files (*)",
        )

        if not filename:
            return False

        # Add .txt when the user did not type an extension.
        if not filename.lower().endswith(".txt"):
            filename += ".txt"

        try:
            with open(filename, "w", encoding="utf-8", newline="\n") as file:
                file.write(">Origami\n\n")
                file.write(text)

            self.exported.emit(
                f"Saved blueprint to:\n{filename}\n\n{text}"
            )
            self.saved.emit(str(Path(filename).parent))
            return True
        

        except OSError as ex:
            QMessageBox.critical(
                parent,
                "Could not save blueprint",
                f"Could not write the file:\n{filename}\n\n{ex}",
            )
            return False


    


    def rows(self):
        """
        RNA-bearing motifs grouped into rows by their connection line.

        Decorative vertical links do not form rows and do not occupy positions
        in the blueprint layout.
        """
        items = [
            item
            for item in self.scene().items()
            if (
                isinstance(item, MotifItem)
                and item.occupies_layout()
            )
        ]

        _, ch = cell_size()
        items.sort(key=lambda item: item.lane_y())

        rows = []

        for item in items:
            if rows and abs(item.lane_y() - rows[-1][0].lane_y()) < 1.5 * ch:
                rows[-1].append(item)
            else:
                rows.append([item])

        for row in rows:
            row.sort(key=lambda item: item.srect().left())

        return rows


    def dropEvent(self, e):
        name = e.mimeData().text()
        item = MotifItem(name)
        vals = getattr(self, "templates", {}).get(name)
        if vals:
            err = item.set_state(values=dict(vals))
            if err:
                self.exported.emit(err)

        self.scene().addItem(item)
        item.setPos(self.mapToScene(e.position().toPoint()))
        item.snap()
        e.acceptProposedAction()


    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.setPen(QPen(QColor("#3a3a3a"), 0, Qt.PenStyle.DotLine))
        for row in self.rows():
            y = row[0].lane_y()
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))





    def normalize_box_heights(self):
        """Boxes always hug their motif text; nothing is padded or shifted."""
        for item in self.scene().items():
            if isinstance(item, MotifItem):
                item.label.setPos(0, 0)
                item.setRect(0, 0, item.natural_width, item.natural_height)
        self.viewport().update()


    

    def selected(self):
        return [i for i in self.scene().selectedItems() if isinstance(i, MotifItem)]

    def keyPressEvent(self, e):
        k = e.key()
        if k in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for it in self.selected():
                self.scene().removeItem(it)

            self.normalize_box_heights()

        elif k == Qt.Key.Key_R:
            changed = False

            for it in self.selected():
                err = it.set_state(rot=(it.rot + 1) % 4)

                if err:
                    self.exported.emit(err)
                else:
                    changed = True

            if changed:
                self.normalize_box_heights()

        elif k == Qt.Key.Key_F:
            changed = False

            for it in self.selected():
                err = it.set_state(flipped=not it.flipped)

                if err:
                    self.exported.emit(err)
                else:
                    changed = True

            if changed:
                self.normalize_box_heights()


        elif k == Qt.Key.Key_E:
            self.exported.emit(self.export())
        elif (
            k == Qt.Key.Key_S
            and e.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            if e.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                self.save_export_with_seq(self.window())
            else:
                self.save_export(self.window())

        elif (
            k == Qt.Key.Key_G
            and e.modifiers() & Qt.KeyboardModifier.ControlModifier
        ):
            self.generate_with_aros(self.window())

        elif k == Qt.Key.Key_H:
            self.exported.emit(self.show_help())

        elif (k == Qt.Key.Key_C
            and e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.copy_selection()

        elif (k == Qt.Key.Key_X
            and e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.cut_selection()

        elif (k == Qt.Key.Key_V
            and e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.paste()

        else:
            super().keyPressEvent(e)

    
    

    

    def zoom_by(self, factor):
        current = self.transform().m11()
        factor = max(MIN_ZOOM / current, min(MAX_ZOOM / current, factor))
        self.scale(factor, factor)

    def wheelEvent(self, e):
        pixel = e.pixelDelta()
        angle = e.angleDelta()
        ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)

        # Touchpad = pixel deltas, or small angle deltas (mouse notches are ±120)
        is_touchpad = (not pixel.isNull()) or (0 < abs(angle.y()) < 120)

        if ctrl or not is_touchpad:
            # Zoom: proportional to the amount scrolled, so small touchpad
            # events give small zooms. (Windows precision touchpads send
            # pinch as Ctrl+wheel, so pinch-to-zoom works there too.)
            delta = pixel.y() if not pixel.isNull() else angle.y()
            self.zoom_by(1.0015 ** delta)
        else:
            # Two-finger scroll pans the canvas
            dx = pixel.x() if not pixel.isNull() else angle.x()
            dy = pixel.y() if not pixel.isNull() else angle.y()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - dx)
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - dy)
        e.accept()

    def viewportEvent(self, e):
        # macOS pinch-to-zoom arrives as a native gesture, not a wheel event
        if e.type() == QEvent.Type.NativeGesture and \
        e.gestureType() == Qt.NativeGestureType.ZoomNativeGesture:
            self.zoom_by(1.0 + e.value())
            return True
        return super().viewportEvent(e)

    def export(self) -> str:
        rows = self.rows()
        if not rows:
            return "Nothing on the canvas."
        cw, _ = cell_size()
        warnings = []
        for n, row in enumerate(rows):
            for a, b in zip(row, row[1:]):
                gap = b.srect().left() - a.srect().right()
                if gap > 1.5 * cw:
                    warnings.append(f"Row {n}: gap between {a.cls_name} and {b.cls_name}")
                elif gap < -1:
                    warnings.append(f"Row {n}: {a.cls_name} overlaps {b.cls_name}")
        layout = "\n".join(f"row {n}: " + "  ".join(i.cls_name for i in row)
                           for n, row in enumerate(rows))
        head = layout + "\n" + ("\n".join(warnings) + "\n" if warnings else "") + "\n"
        try:
            ori = pf.Origami([[i.motif for i in row] for row in rows],
                             align="center", copy=True)
            return f"Sequence: {ori.sequence}\n\nStructure: {ori.structure}\n\n{ori}\n\n{head}"
        except Exception as ex:
            return f"{head}Could not assemble: {type(ex).__name__}: {ex}"

    def show_help(self):
        print("Flip motifs: F")
        print("Rotate motifs: R")
        print("Preview Blueprint: E")
        print("Generate Sequence: CTRL + G")
        print("Save Blueprint: CTRL + S")
        print("Save Blueprint with sequence: CTRL + Shift + S")

        return "Flip motifs : F\nRotate motifs: R\nPreview Blueprints: E\nGenerate Sequence: CTRL + G\nSave Blueprint: CTRL + S\nSave Blueprint with sequence: CTRL + Shift + S"





def main():
    app = QApplication.instance() or QApplication(sys.argv)

    canvas = Canvas()
    palette = Palette()
    props = PropertiesPanel()
    out = QPlainTextEdit()

    out.setReadOnly(True)
    out.setFont(mono_font())

    canvas.exported.connect(out.setPlainText)
    palette.itemClicked.connect(lambda it: props.show_class(it.text()))

    def on_selection():
        selected = canvas.selected()
        props.show_item(selected[0] if len(selected) == 1 else None)

    canvas.scene().selectionChanged.connect(on_selection)
    canvas.motif_edited.connect(props.show_item)
    canvas.templates = props.templates
    palette.itemClicked.connect(lambda it: props.show_class(it.text()))

    left = QSplitter(Qt.Orientation.Vertical)
    left.addWidget(palette)
    left.addWidget(props)
    left.setSizes([220, 480])

    right = QSplitter(Qt.Orientation.Vertical)
    right.addWidget(canvas)
    right.addWidget(out)
    right.setSizes([520, 200])

    split = QSplitter()
    split.addWidget(left)
    split.addWidget(right)
    split.setSizes([300, 800])

    window = QMainWindow()
    runner = RopeRunner(window)
    runner.output.connect(lambda s: (out.moveCursor(out.textCursor().MoveOperation.End),
                                     out.insertPlainText(s)))
    #runner.finished.connect(lambda code, d: (
    #    out.appendPlainText(f"\n[finished, exit code {code}]  results: {d}")
        #QDesktopServices.openUrl(QUrl.fromLocalFile(d))
    #    ))   

    def on_finished(code, workdir):
        out.appendPlainText(f"\n[finished, exit code {code}]  results: {workdir}")
        if runner.current_exe == "rope-build" and code == 0:
            n = props.viewer.load_folder(workdir)
            if n:
                props.tabs.setCurrentWidget(props.viewer)
                out.appendPlainText(f"Loaded {n} PDB files into 3D viewer.")
            else:
                out.appendPlainText("No PDB files found in results folder.")
    runner.finished.connect(on_finished)
    canvas.saved.connect(lambda folder: setattr(runner, "base_dir", Path(folder)))

    def choose_results_folder():
            d = QFileDialog.getExistingDirectory(window, "Choose results folder")
            if d:
                runner.base_dir = Path(d)
                out.appendPlainText(f"Results folder: {d}")
    def run_tool(exe):
        tool = TOOLS[exe]
        dlg = OptionsDialog(tool, window)
        if not dlg.exec():
            return
        try:
            text = canvas.blueprint_text() if tool.needs_input else None
            if text and exe == "rope-build":
                text = randomize_blueprint(text)
        except Exception as ex:
            out.setPlainText(f"Cannot run {exe}: {type(ex).__name__}: {ex}")
            return
        runner.run(tool, dlg.args(), text)

    menu = window.menuBar().addMenu("&Tools")
    for exe, tool in TOOLS.items():
        act = QAction(f"{tool.title}  ({exe})", window)
        act.triggered.connect(lambda _=False, e=exe: run_tool(e))
        menu.addAction(act)
    menu.addSeparator()
    stop = QAction("Stop running job", window)
    stop.triggered.connect(runner.stop)
    

    pick = QAction("Set results folder...", window)
    pick.triggered.connect(choose_results_folder)
    menu.addAction(pick)
    menu.addAction(stop)
    window.setWindowTitle("Blueprint Designer")
    window.setCentralWidget(split)
    window.resize(1200, 780)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())