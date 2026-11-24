"""
Blueprint Designer: GUI frontend.

All RNA/origami logic lives in the backend module (currently PyFurnace).
To switch backends, change the single `backend` import below.
"""
from __future__ import annotations
import six.moves, matplotlib.pyplot
import PyFurnace_logic as backend

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import (QEvent, QLineF, QMimeData, QObject, QPointF, QProcess,
                            QProcessEnvironment, Qt, QUrl, Signal)
from PySide6.QtGui import (QAction, QBrush, QColor, QCursor, QFont,
                           QFontMetricsF, QPen)
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFileDialog, QFormLayout, QGraphicsItem,
    QGraphicsRectItem, QGraphicsScene, QGraphicsSimpleTextItem, QGraphicsView,
    QInputDialog, QLabel, QLineEdit, QListWidget, QMainWindow, QMessageBox,
    QPlainTextEdit, QSpinBox, QSplitter, QTabWidget, QVBoxLayout, QWidget,
)




DRAG_THRESHOLD = 5
SNAP_DIST = 10   
MIN_ZOOM, MAX_ZOOM = 0.2, 5.0
CLIP_MARKER = "blueprint-designer-motifs"
AROS_TIMEOUT = 1200  




def mono_font():
    f = QFont("Menlo")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setFixedPitch(True)
    f.setPointSize(11)
    return f


def cell_size():
    """Pixel size of one monospaced text cell (width, line spacing)."""
    fm = QFontMetricsF(mono_font())
    return fm.horizontalAdvance("M"), fm.lineSpacing()


def rows_overlap(a, b):
    return not (a.bottom() <= b.top() or a.top() >= b.bottom())


# =============================================================================
# AROS (bundled sequence designer, independent of the RNA backend)
# =============================================================================

def application_dir():
    """Folder that contains main.py, bin/ and misc/."""
    return Path(__file__).resolve().parent


APP_DIR = application_dir()


def aros_binary_path():
    """Return the AROS executable bundled for the current platform."""
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


def ensure_executable(path):
    """Confirm that the bundled AROS binary exists and is executable."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"AROS executable not found:\n{path}\n\n"
            "Check that the appropriate binary is present in the bin folder."
        )
    if os.name != "nt":
        path.chmod(path.stat().st_mode | 0o111)
    return path


def write_aros_input(sequence, structure, path):
    """Write the input format consumed by AROS (equal-length seq + structure)."""
    sequence = "".join(sequence.split())
    structure = "".join(structure.split())

    if len(sequence) != len(structure):
        raise ValueError(
            f"Sequence and structure must have the same length: "
            f"{len(sequence)} != {len(structure)}"
        )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"Sequence:{sequence}\nStructure:{structure}\n", encoding="utf-8")
    return path


def read_aros_outputs(output_dir=AROS_OUTPUT_DIR):
    """Read all AROS result files below misc/output/, best candidate first."""
    output_dir = Path(output_dir)

    if not output_dir.is_dir():
        raise FileNotFoundError(f"AROS output directory does not exist:\n{output_dir}")

    files = sorted(p for p in output_dir.rglob("*.txt") if p.is_file())
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

        for raw_line in output_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if ":" not in line:          
                continue

            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "sequence":
                sequence = "".join(value.split()).upper()
            elif key == "target":
                target_structure = "".join(value.split())
            elif key == "mfe structure":
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
            "AROS created output files, but none matched the expected AROS result format."
        )

    return sorted(
        candidates,
        key=lambda c: (c["bp_distance"], c["ensemble_diversity"], c["filename"]),
    )




class OptionsDialog(QDialog):
    def __init__(self, tool, parent=None):
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
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def args(self) -> list[str]:
        out = []
        for o in self.tool.opts:
            w = self.widgets[o.flag]
            v = w.text().strip() if isinstance(w, QLineEdit) else w.value()
            if v == "":
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
        self.current_tool = None

    def running(self):
        return self.proc is not None and self.proc.state() != QProcess.NotRunning

    def run(self, tool, args: list[str], blueprint_text: str | None):
        if self.running():
            self.output.emit("A job is already running. Stop it first.\n")
            return
        try:
            exe = backend.find_exe(tool.exe)
        except FileNotFoundError as ex:
            self.output.emit(f"{ex}\n")
            return

        if self.base_dir is None:
            self.base_dir = Path(tempfile.gettempdir())      # fallback
        self.workdir = tempfile.mkdtemp(prefix=f"{tool.exe}_", dir=self.base_dir)
        self.current_exe = tool.exe
        self.current_tool = tool
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


# =============================================================================
# Canvas items
# =============================================================================

class MotifItem(QGraphicsRectItem):
    def __init__(self, cls_name):
        super().__init__()
        self.cls_name = cls_name
        self.params = backend.specs(cls_name)
        self.values = backend.default_values(cls_name)
        self.rot, self.flipped, self.motif = 0, False, None   # motif: backend.BuiltMotif
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setPen(QPen(QColor("#555"), 0))
        self.setBrush(QBrush(QColor(backend.COLORS.get(cls_name, "#ddd"))))
        self.label = QGraphicsSimpleTextItem(self)
        self.label.setFont(mono_font())
        self.label.setBrush(QBrush(QColor("black")))
        self.row_span = backend.row_span(cls_name)

        self.natural_width = 0
        self.natural_height = 0
        self.anchor_row = None

        self.resize_margin = 8      # px grab zone on the right edge
        self.resizing = False
        self.resize_x0 = 0
        self.resize_len0 = 0
        self.setAcceptHoverEvents(True)

        self.rebuild()

    # --- kind -----------------------------------------------------------------
    def is_decorative(self):
        """Drawn, but not part of the assembled RNA model."""
        return backend.is_decorative(self.cls_name)

    def occupies_layout(self):
        return not self.is_decorative()

    # --- junction geometry ----------------------------------------------------
    def lane_y(self):
        """Scene y of the top-most horizontal junction = this motif's row."""
        _, ch = cell_size()
        edges = self.motif.edges or {}
        ys = [y for e in ("L", "R") for _, y in edges.get(e, [])]
        if not ys:
            return self.srect().center().y()
        top = self.label.boundingRect().top()
        return self.label.mapToScene(QPointF(0, top + (min(ys) + 0.5) * ch)).y()

    def junction_scene_pos(self, junction):
        """Center of a junction cell in scene coordinates."""
        col, row = junction
        cw, ch = cell_size()
        text_rect = self.label.boundingRect()
        local_point = QPointF(
            text_rect.left() + (col + 0.5) * cw,
            text_rect.top() + (row + 0.5) * ch,
        )
        return self.label.mapToScene(local_point)

    # --- mouse: drag right edge to resize, otherwise move + snap ---------------
    def can_resize(self):
        return (self.cls_name in backend.RESIZE_PARAM
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
            self.resize_len0 = self.values[backend.RESIZE_PARAM[self.cls_name]]
            self.setSelected(True)
            e.accept()
            return
        self._press_pos = e.scenePos()
        self._dragging = False
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.resizing:
            key = backend.RESIZE_PARAM[self.cls_name]
            p = next(p for p in self.params if p.name == key)
            cw, _ = cell_size()
            sign = -1 if self.resize_len0 < 0 else 1          # dovetail direction
            n = abs(self.resize_len0) + round((e.scenePos().x() - self.resize_x0) / cw)
            n = max(1, min(max(abs(p.lo), abs(p.hi)), n))
            if sign * n != self.values[key]:
                self.set_state(values={**self.values, key: sign * n})  # pushes neighbours
            e.accept()
            return
        if not getattr(self, "_dragging", False):
            delta = e.scenePos() - self._press_pos
            if abs(delta.x()) + abs(delta.y()) < DRAG_THRESHOLD:
                e.accept()
                return
            self._dragging = True
        super().mouseMoveEvent(e)
        ghost, t = self.scene().ghost, self.find_snap()
        if t is not None:
            ghost.setRect(t.x(), t.y(), self.rect().width(), self.rect().height())
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

    # --- model ----------------------------------------------------------------
    def rebuild(self):
        """Construct the motif first; only commit if nothing raised."""
        m = backend.build_motif(self.cls_name, self.values, self.rot, self.flipped)
        self.motif = m
        self.anchor_row = m.anchor_row

        lines = m.text.splitlines() or [""]
        cw, ch = cell_size()

        self.label.setText(m.text)
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

    # --- geometry -------------------------------------------------------------
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
            horizontal_overlap = not (r.right() <= me.left() or r.left() >= me.right())
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
        mine = self.motif.edges
        if not mine:
            return None

        me = self.srect()
        others = [
            item for item in self.scene().items()
            if (isinstance(item, MotifItem) and item is not self
                and item.motif is not None and item.occupies_layout())
        ]

        best, best_d = None, float("inf")
        for other in others:
            theirs = other.motif.edges
            if not theirs:
                continue
            r = other.srect()

            # (my edge, their edge, axis, new left, new top)
            configs = [
                ("L", "R", "h", r.right(),             None),
                ("R", "L", "h", r.left() - me.width(), None),
                ("T", "B", "v", None,                  r.bottom()),
                ("B", "T", "v", None,                  r.top() - me.height()),
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
                        if (self.occupies_layout()
                                and any(target.adjusted(1, 1, -1, -1).intersects(o.srect())
                                        for o in others)):
                            continue         # that slot is already occupied
                        best, best_d = QPointF(self.x() + dx, self.y() + dy), d
        return best

    def snap(self):
        target = self.find_snap()
        if target is not None:
            self.setPos(target)
            return
        cw, ch = cell_size()
        self.setPos(round(self.x() / cw) * cw, round(self.y() / ch) * ch)


# =============================================================================
# 3D viewer
# =============================================================================

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


# =============================================================================
# Properties panel + palette
# =============================================================================

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
        vals = self.templates.setdefault(cls_name, backend.default_values(cls_name))
        for p in backend.specs(cls_name):
            w = self._make(p, vals[p.name])
            self.widgets[p.name] = w
            self.form.addRow(p.name, w)
        self.cls_name = cls_name
        self.update_preview()

    def update_preview(self):
        try:
            m = backend.build_motif(
                self.cls_name, {n: self._read(w) for n, w in self.widgets.items()})
            self.info.setPlainText(f"{m}\n\nsequence:  {m.sequence}\nstructure: {m.structure}")
            self.error.clear()
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
        self.addItems(backend.motif_names())
        self.setDragEnabled(True)
        self.setDragDropMode(QListWidget.DragDropMode.DragOnly)

    def mimeData(self, items):
        m = QMimeData()
        m.setText(items[0].text())
        return m


# =============================================================================
# Canvas
# =============================================================================

class Canvas(QGraphicsView):
    exported = Signal(str)
    motif_edited = Signal(object)
    saved = Signal(str)

    _paste_count = 0
    _copy_origin = (0.0, 0.0)

    def __init__(self):
        super().__init__()

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

    # --- drag & drop ----------------------------------------------------------
    def dragEnterEvent(self, e): e.acceptProposedAction()
    def dragMoveEvent(self, e):  e.acceptProposedAction()

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

    # --- clipboard ------------------------------------------------------------
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
            if cls not in backend.SPECS:
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

    # --- layout ---------------------------------------------------------------
    def selected(self):
        return [i for i in self.scene().selectedItems() if isinstance(i, MotifItem)]

    def rows(self):
        """RNA-bearing motifs grouped into rows by their connection line."""
        items = [i for i in self.scene().items()
                 if isinstance(i, MotifItem) and i.occupies_layout()]

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

    def normalize_box_heights(self):
        """Boxes always hug their motif text; nothing is padded or shifted."""
        for item in self.scene().items():
            if isinstance(item, MotifItem):
                item.label.setPos(0, 0)
                item.setRect(0, 0, item.natural_width, item.natural_height)
        self.viewport().update()

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.setPen(QPen(QColor("#3a3a3a"), 0, Qt.PenStyle.DotLine))
        for row in self.rows():
            y = row[0].lane_y()
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))

    # --- backend-facing: assembly / export -------------------------------------
    def origami(self):
        """
        Assemble RNA-bearing motifs through the backend (returns an Assembly).
        Decorative items are excluded from the sequence/structure.
        """
        motif_rows = [
            [item.motif for item in row if item.occupies_layout()]
            for row in self.rows()
        ]
        motif_rows = [row for row in motif_rows if row]

        if not motif_rows:
            raise ValueError(
                "Nothing RNA-bearing is on the canvas; only decorative links exist."
            )
        return backend.assemble(motif_rows, align="left")

    def aros_input(self):
        """Current assembled sequence and dot-bracket structure."""
        ori = self.origami()
        sequence = "".join(ori.sequence.split())
        structure = "".join(ori.structure.split())

        if len(sequence) != len(structure):
            raise ValueError(
                "The assembled sequence and structure have different "
                f"lengths: {len(sequence)} != {len(structure)}"
            )
        return sequence, structure

    def blueprint_text(self):
        """Blueprint as the external tools expect it: drawing with 5'/3' markers."""
        self.origami()                      # raises if nothing RNA-bearing / can't assemble
        text = self.export()
        try:
            text, _ = backend.fill_blueprint(text)   # no design -> only adds 5'/3' markers
        except backend.BlueprintError as ex:
            raise ValueError(f"Could not mark the 5'/3' ends: {ex}")
        return ">Origami\n\n" + text

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
            ori = backend.assemble([[i.motif for i in row] for row in rows],
                                   align="center")
            return f"Sequence: {ori.sequence}\n\nStructure: {ori.structure}\n\n{ori.text}\n\n{head}"
        except Exception as ex:
            return f"{head}Could not assemble: {type(ex).__name__}: {ex}"

    # --- AROS -----------------------------------------------------------------
    def clear_aros_outputs(self, output_dir=AROS_OUTPUT_DIR):
        """Remove previous run_* folders so old results are not mixed in."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        for path in output_dir.iterdir():
            if path.is_dir() and path.name.startswith("run_"):
                shutil.rmtree(path)

    def get_aros_settings(self, parent=None):
        """Values AROS asks for interactively: complete runs, hill-climbing starts."""
        runs, ok = QInputDialog.getInt(
            parent, "AROS configuration", "Complete runs:", 3, 1, 1000, 1)
        if not ok:
            return None
        starts, ok = QInputDialog.getInt(
            parent, "AROS configuration", "Hill-climbing starts per run:", 5, 1, 10000, 1)
        if not ok:
            return None
        return runs, starts

    def aros_candidates(self, runs, starts):
        """
        Write the assembled design to AROS input, run the bundled executable and
        return (candidates best-first, AROS stdout). Raises on any failure.
        """
        executable = ensure_executable(AROS_BIN)

        sequence, structure = self.aros_input()
        write_aros_input(sequence, structure, path=AROS_INPUT_FILE)

        aros_stdin = f"{runs}\n{starts}\n"
        env = {**os.environ, "RUST_BACKTRACE": "1"}

        self.clear_aros_outputs()

        result = subprocess.run(
            [str(executable)],
            cwd=APP_DIR,
            input=aros_stdin,
            text=True,
            capture_output=True,
            timeout=AROS_TIMEOUT,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"AROS failed with exit code {result.returncode}.\n\n"
                f"stdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            )

        return read_aros_outputs(AROS_OUTPUT_DIR), result.stdout

    def run_aros(self, runs, starts):
        """Run AROS and return a text report about the best candidate."""
        candidates, stdout = self.aros_candidates(runs, starts)
        best = candidates[0]

        summary = "\n".join(
            f"# {number}. {c['filename']}  "
            f"bp_distance={c['bp_distance']}, "
            f"Ensemble Diversity={c['ensemble_diversity']}"
            for number, c in enumerate(candidates, start=1)
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

    def generate_with_aros(self, parent=None):
        """Ask for AROS run settings, execute AROS, and show the best result."""
        settings = self.get_aros_settings(parent)
        if settings is None:
            return
        runs, starts = settings

        try:
            self.exported.emit(self.run_aros(runs, starts))

        except subprocess.TimeoutExpired:
            message = (f"AROS timed out after {AROS_TIMEOUT} seconds.\n"
                       "Try fewer complete runs or fewer hill-climbing starts.")
            self.exported.emit(message)
            if parent is not None:
                QMessageBox.warning(parent, "AROS timed out", message)

        except Exception as ex:
            message = f"AROS generation failed:\n{type(ex).__name__}: {ex}"
            self.exported.emit(message)
            if parent is not None:
                QMessageBox.critical(parent, "AROS generation failed", message)

    # --- saving ---------------------------------------------------------------
    def save_export(self, parent=None):
        """Export the current blueprint and save it as a UTF-8 .txt file."""
        text = self.export()

        filename, _ = QFileDialog.getSaveFileName(
            parent, "Save blueprint", "blueprint.txt",
            "Text files (*.txt);;All files (*)")
        if not filename:
            return False
        if not filename.lower().endswith(".txt"):
            filename += ".txt"

        try:
            with open(filename, "w", encoding="utf-8", newline="\n") as file:
                file.write(">Origami\n\n")
                file.write(text)

            self.exported.emit(f"Saved blueprint to:\n{filename}\n\n{text}")
            self.saved.emit(str(Path(filename).parent))
            return True

        except OSError as ex:
            QMessageBox.critical(
                parent, "Could not save blueprint",
                f"Could not write the file:\n{filename}\n\n{ex}")
            return False

    def save_export_with_seq(self, parent=None):
        """
        Export the blueprint, design a sequence with AROS, write the best
        candidate into the blueprint and save it as a UTF-8 .txt file.
        Returns True on success, False if cancelled or anything failed.
        """
        # 1. fail early if the design can't be assembled
        try:
            text = self.export()
            self.aros_input()
        except Exception as ex:
            QMessageBox.critical(parent, "Cannot design a sequence",
                                 f"{type(ex).__name__}: {ex}")
            return False

        # 2. ask for the file name BEFORE the (slow) AROS run
        filename, _ = QFileDialog.getSaveFileName(
            parent, "Save blueprint with sequence", "blueprint_with_seq.txt",
            "Text files (*.txt);;All files (*)")
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

            design_text = (f"sequence : {best['sequence']}\n"
                           f"target : {best['structure']}\n")
            filled, warnings = backend.fill_blueprint(text, design_text)

        except subprocess.TimeoutExpired:
            message = (f"AROS timed out after {AROS_TIMEOUT} seconds.\n"
                       "Try fewer complete runs or fewer hill-climbing starts.")
            self.exported.emit(message)
            QMessageBox.warning(parent, "AROS timed out", message)
            return False
        except backend.BlueprintError as ex:
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
                file.write(filled)
        except OSError as ex:
            QMessageBox.critical(parent, "Could not save blueprint",
                                 f"Could not write the file:\n{filename}\n\n{ex}")
            return False

        report = (f"Saved blueprint with sequence to:\n{filename}\n\n"
                  f"Selected {best['filename']}  "
                  f"(bp_distance={best['bp_distance']}, "
                  f"Ensemble Diversity={best['ensemble_diversity']})\n")
        if warnings:
            report += "\nWarnings:\n" + "\n".join(f"  {w}" for w in warnings) + "\n"
        self.exported.emit(f"{report}\n{filled}")
        self.saved.emit(str(Path(filename).parent))
        return True

    # --- keyboard -------------------------------------------------------------
    def keyPressEvent(self, e):
        k = e.key()
        ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)
        shift = bool(e.modifiers() & Qt.KeyboardModifier.ShiftModifier)

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

        elif k == Qt.Key.Key_S and ctrl:
            if shift:
                self.save_export_with_seq(self.window())
            else:
                self.save_export(self.window())

        elif k == Qt.Key.Key_G and ctrl:
            self.generate_with_aros(self.window())

        elif k == Qt.Key.Key_H:
            self.exported.emit(self.show_help())

        elif k == Qt.Key.Key_C and ctrl:
            self.copy_selection()

        elif k == Qt.Key.Key_X and ctrl:
            self.cut_selection()

        elif k == Qt.Key.Key_V and ctrl:
            self.paste()

        else:
            super().keyPressEvent(e)

    # --- zoom / pan -----------------------------------------------------------
    def zoom_by(self, factor):
        current = self.transform().m11()
        factor = max(MIN_ZOOM / current, min(MAX_ZOOM / current, factor))
        self.scale(factor, factor)

    def wheelEvent(self, e):
        pixel = e.pixelDelta()
        angle = e.angleDelta()
        ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)

        # Touchpad = pixel deltas, or small angle deltas (mouse notches are +-120)
        is_touchpad = (not pixel.isNull()) or (0 < abs(angle.y()) < 120)

        if ctrl or not is_touchpad:
            # Zoom proportional to the amount scrolled. (Windows precision
            # touchpads send pinch as Ctrl+wheel, so pinch-to-zoom works too.)
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
        if (e.type() == QEvent.Type.NativeGesture
                and e.gestureType() == Qt.NativeGestureType.ZoomNativeGesture):
            self.zoom_by(1.0 + e.value())
            return True
        return super().viewportEvent(e)

    def show_help(self):
        text = ("Flip motifs : F\n"
                "Rotate motifs: R\n"
                "Preview Blueprints: E\n"
                "Generate Sequence: CTRL + G\n"
                "Save Blueprint: CTRL + S\n"
                "Save Blueprint with sequence: CTRL + Shift + S")
        print(text)
        return text


# =============================================================================
# Main window
# =============================================================================

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

    def on_finished(code, workdir):
        out.appendPlainText(f"\n[finished, exit code {code}]  results: {workdir}")
        tool = runner.current_tool
        if tool is not None and tool.produces_pdb and code == 0:
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
        tool = backend.TOOLS[exe]
        dlg = OptionsDialog(tool, window)
        if not dlg.exec():
            return
        try:
            text = canvas.blueprint_text() if tool.needs_input else None
            if text and tool.randomize_ambiguous:
                text = backend.randomize_blueprint(text)
        except Exception as ex:
            out.setPlainText(f"Cannot run {exe}: {type(ex).__name__}: {ex}")
            return
        runner.run(tool, dlg.args(), text)

    menu = window.menuBar().addMenu("&Tools")
    for exe, tool in backend.TOOLS.items():
        act = QAction(f"{tool.title}  ({exe})", window)
        act.triggered.connect(lambda _=False, e=exe: run_tool(e))
        menu.addAction(act)
    menu.addSeparator()

    pick = QAction("Set results folder...", window)
    pick.triggered.connect(choose_results_folder)
    menu.addAction(pick)

    stop = QAction("Stop running job", window)
    stop.triggered.connect(runner.stop)
    menu.addAction(stop)

    window.setWindowTitle("Blueprint Designer")
    window.setCentralWidget(split)
    window.resize(1200, 780)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())