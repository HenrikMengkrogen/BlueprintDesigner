# Blueprint Designer

A desktop GUI for drawing RNA origami blueprints. Drag motifs from a palette onto a canvas, snap them together at their junctions, and Blueprint Designer assembles them into a [pyFuRNAce](https://github.com/dahl-lab/pyfurnace) `Origami` object. From there you can export the blueprint, design a sequence for it with **AROS**, and run the **ROPE** tools (sequence prediction, 3D building, blueprint flipping), all from one window.

Built with PySide6 (Qt).

## Features

- **Motif palette**: stems, dovetails, loops, tetraloops, kissing loops and dimers, aptamers (Mango, Broccoli, Pepper, Malachite Green, ...), protein-binding motifs (MS2, PP7, Streptavidin, ...), junctions, and more. Only motifs exported by your installed pyFuRNAce version are shown.
- **Snap-to-junction layout**: motifs snap to compatible left/right and top/bottom junctions, with a green ghost outline previewing the snap target.
- **Live properties panel**: edit sequence, length, wobble settings, loop orientation, pseudoknot index, etc. The motif updates immediately and neighbours are pushed aside when its size changes.
- **Live preview**: the Info tab shows the motif's drawing, sequence and structure.
- **AROS sequence design**: generate a sequence for the assembled structure and write it back into the blueprint.
- **ROPE integration**: run `rope-fold`, `rope-dragon`, `rope-build` and `rope-flip` on the current blueprint, with output streamed into the log pane.
- **3D viewer**: PDB files produced by `rope-build` are loaded into an embedded 3Dmol.js viewer.
- **Copy / cut / paste** of motif selections, with touchpad pan and pinch-to-zoom.

## Requirements

- Linux or macOS with `bash`, `git` and `python3` (the setup script is a bash script).
- Python 3.9+ (3.10+ recommended).
- Internet access during setup (clones ROPE, installs from PyPI).
- A bundled AROS binary for your platform in `bin/`:

  | OS      | Expected file          |
  |---------|------------------------|
  | macOS   | `bin/aros-macos`       |
  | Linux   | `bin/aros-linux`       |
  | Windows | `bin/aros-windows.exe` |

## Installation

Run the setup script from inside the `Blueprint_Designer` folder:

```bash
chmod +x setup.sh      
./setup.sh
```

The script does the following:

1. Moves to the parent directory and clones [ROPE](https://github.com/nikolaj-zwergius/ROPE) into `../ROPE`.
2. Installs ROPE in editable mode (`python3 install.py --mode edit`).
3. Replaces `rope/core/Build_logic.py` and `rope/core/trace_logic.py` in the ROPE checkout with the patched versions from `build_logic.txt` and `trace_logic.txt`, then deletes those two `.txt` files from `Blueprint_Designer`.
4. Creates a virtual environment in `.venv/` (if it does not already exist).
5. Installs `PySide6` and `pyfurnace` into that environment and verifies the imports.

Afterwards, activate the environment:

```bash
source .venv/bin/activate
```

### Notes

- **The script is not re-runnable.** It clones into `../ROPE` and consumes `build_logic.txt` / `trace_logic.txt`. To run it again, delete `../ROPE` and restore those two files first.
- **ROPE is installed with the system `python3`, not the `.venv`.** The app looks for `rope-*` executables on your `PATH`, then next to the Python interpreter running the app. If the Tools menu reports that a `rope-*` tool was not found, either install ROPE inside the virtual environment (activate `.venv`, then run `python install.py --mode edit` in the ROPE folder) or make sure the system scripts folder is on your `PATH`.

## Running

With the environment active, start the application from the project root:

```bash
blueprint-designer
```



## Project layout

The app resolves its resource paths relative to the project root (two levels above the script):

```
Blueprint_Designer/
├── bin/
│   ├── aros-macos
│   ├── aros-linux
│   └── aros-windows.exe
├── misc/
│   ├── input_1.txt        # written by the app as AROS input
│   ├── output/            # AROS writes run_*/ result folders here
│   └── 3Dmol-min.js       # optional local copy; falls back to the 3dmol.org CDN
└── ...
```

AROS reads `misc/input_1.txt` and writes to `misc/output/`. These paths must match what the AROS binary is configured to use. Old `output/run_*` folders are deleted before each AROS run.

## Usage

### Building a blueprint

1. Click a motif in the palette to edit its **template** values, then drag it onto the canvas.
2. Drop motifs near each other; they snap together when their junctions are compatible. Motifs in the same horizontal lane form one row of the blueprint.
3. Select a motif to edit its parameters in the properties panel.
4. Drag the **right edge** of a `Stem` or `Dovetail` to change its length (only when it is not rotated and has no explicit sequence).
5. Press **E** to preview the assembled sequence, structure and drawing in the log pane. Gaps or overlaps between neighbouring motifs are reported as warnings.

`vertical_link` and `vertical_double_link` are decorative only: they appear on the canvas but are excluded from the assembled RNA model.

### Keyboard shortcuts

| Key                | Action                                         |
|--------------------|------------------------------------------------|
| `R`                | Rotate selected motif(s)                       |
| `F`                | Flip selected motif(s) horizontally            |
| `E`                | Preview the blueprint                          |
| `H`                | Show help                                      |
| `Delete` / `Backspace` | Delete selection                           |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | Copy / cut / paste motifs          |
| `Ctrl+S`           | Save blueprint as `.txt`                       |
| `Ctrl+Shift+S`     | Design a sequence with AROS, then save         |
| `Ctrl+G`           | Generate a sequence with AROS and show it      |

On macOS, use `Cmd` in place of `Ctrl` only if your Qt build maps it; the app checks for Qt's `ControlModifier`.

Navigation: scroll or two-finger drag to pan, `Ctrl` + scroll (or pinch) to zoom, drag on empty canvas for rubber-band selection.

### Designing a sequence with AROS

Press `Ctrl+G` (show result) or `Ctrl+Shift+S` (save to file). You are prompted for:

- **Complete runs** (default 3)
- **Hill-climbing starts per run** (default 5)

Candidates are ranked by base-pair distance, then ensemble diversity. The best one is written into the blueprint as `Sequence` and `Structure` lines. AROS runs are limited to 20 minutes; reduce the number of runs or starts if it times out.

### ROPE tools

Open the **Tools** menu:

| Menu entry                       | Command        | Options                                  |
|----------------------------------|----------------|------------------------------------------|
| Predict sequences (batch)        | `rope-fold`    | runs, workers                            |
| Predict sequences (continuous)   | `rope-dragon`  | runs, workers, ensemble diversity, time per run |
| Build PDB files                  | `rope-build`   | ligand (`MODULE=LIGAND`)                 |
| Flip blueprint                   | `rope-flip`    | none                                     |

Each run gets its own temporary working folder containing `blueprint.txt`, and live output appears in the log pane. For `rope-build`, ambiguous bases (N, K, S, ...) are first replaced with random nucleotides, keeping paired positions complementary (including G-U wobbles). When the build finishes, the resulting PDB files load into the **3D** tab.

Use **Tools → Set results folder...** to choose where run folders are created. After you save a blueprint, its folder becomes the default results location. **Tools → Stop running job** terminates the current process.

## Troubleshooting

- **`AROS executable not found`**: check that the binary for your OS exists in `bin/` with the exact filename listed above.
- **`rope-* not found`**: see the installation notes about which Python environment ROPE was installed into.
- **`Skipped (not found in pf)` at startup**: your pyFuRNAce version does not export some motif classes; those motifs are hidden from the palette. Upgrading pyFuRNAce may help.
- **`Could not assemble` in the preview**: the motifs on the canvas do not form a valid row layout. Check the gap/overlap warnings listed above the error.
- **3D viewer is blank**: the viewer loads `misc/3Dmol-min.js` if present, otherwise it needs internet access to fetch 3Dmol.js. Check the terminal for `[JS]` console messages.

## Acknowledgements

Built on [pyFuRNAce](https://github.com/dahl-lab/pyfurnace), [ROPE](https://github.com/nikolaj-zwergius/ROPE), AROS, [3Dmol.js](https://3dmol.org) and [Qt for Python (PySide6)](https://doc.qt.io/qtforpython-6/).
