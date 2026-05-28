## Before You Begin: Install setuptools

The CT-CatPhan project uses setupstools as its build backend. Therefore, to use CT-CatPhan in editable/development mode, you must have the setuptools package installed in your Python environment **before** running:

    pip install -e .

Why is this required?
- Editable installs (the -e flag) need setuptools to link your source code to your environment so changes are reflected immediately.
- The command-line tool `catphan500` and other entry points are only created if setuptools is present.
- Some packaging features (like versioning and plugin discovery) depend on setuptools.

If you see errors about missing setuptools or entry points, install it first:

    pip install setuptools

---

# Quick Start

This guide is the shortest path to getting started with CT-CatPhan.

Use this document if you are brand new to the repository and want either:

- a quick path to running CatPhan analysis, or
- a quick path to starting development work.

The public package and CLI surface are both named `catphan500`.

## 1. Install the Package

From the repository root:

```powershell
python -m pip install -e .
```

If you also plan to build the docs locally:

```powershell
python -m pip install -e .[docs]
```

## 2. Choose Your Path

### Path A: Run Analysis Quickly

If you want to analyze a CatPhan DICOM series right away, use the CLI.

Open the folder picker and run the full workflow:

```powershell
catphan500 -m full_analysis --plot
```

If you want the uniformity module to use the mirror-correlation center finder
instead of the default edge-based method:

```powershell
catphan500 -m full_analysis --plot --center-algorithm mirror
```

Or run against a known DICOM folder:

```powershell
catphan500 C:\path\to\dicom_folder -m full_analysis --plot --save-plot results
```

What this does:

- loads the DICOM series,
- runs the full module workflow,
- writes a JSON results file, and
- generates per-module plots.

Common CLI qualifiers in these examples:

- `-m` or `--modules`: chooses which module workflows to run. Use `full_analysis` for the standard end-to-end sequence.
- `--plot`: generates diagnostic figures for the modules that ran.
- `--save-plot <path>`: writes PNG plot files either into an existing directory or with a filename prefix.
- `--show-plot`: opens plots interactively instead of only saving them.
- `--center-algorithm edge|mirror`: controls how the uniformity module finds the phantom center. `mirror` is intended for the symmetric CTP486 slice.
- `--average-slices`: averages each target slice with its neighbors in DICOM-series mode to reduce noise.
- `--single-image`: analyzes one image file instead of loading a full DICOM folder.
- `-o` or `--out`: chooses the JSON output path explicitly.
- `--no-save`: runs the analysis without writing a JSON file.

Practical examples:

- `catphan500 -m full_analysis --plot`: run the standard workflow and create plots.
- `catphan500 -m full_analysis --plot --center-algorithm mirror`: keep the standard workflow but use mirror correlation for the uniformity center.
- `catphan500 C:\path\to\dicom_folder -m full_analysis --plot --save-plot results -o results\full_analysis.json`: run against a known folder and save both JSON and plots to explicit locations.
- `catphan500 C:\path\to\slice.dcm --single-image -m uniformity --plot`: use the legacy single-image path for one module.

If you only want a few modules:

```powershell
catphan500 C:\path\to\dicom_folder -m uniformity detailed_uniformity ctp401
```

### Path B: Use the Python API

If you want to script the analysis in Python:

```python
from catphan500 import Catphan500Analyzer, load_dicom_series

series = load_dicom_series(r"C:\path\to\dicom_folder")
analyzer = Catphan500Analyzer(
   dicom_series=series,
   use_slice_averaging=True,
   center_algorithm="mirror",
)

results = analyzer.run_full_analysis()
analyzer.save_results_json("results.json")

print(results.keys())
```

### Path C: Start Development Work

If your goal is to work on the package itself:

1. Install in editable mode:

   ```powershell
   python -m pip install -e .
   ```

2. Read the main package files:

   - `src/catphan500/analysis.py`
   - `src/catphan500/cli.py`
   - `src/catphan500/io.py`

3. If you are working on documentation too, install the docs extra:

   ```powershell
   python -m pip install -e .[docs]
   ```

4. Build the docs locally when needed:

   ```powershell
   python -m sphinx -b html docs docs/_build/html
   ```

## 3. Know the Main Entry Points

- CLI entry point: `catphan500`
- Main analyzer class: `Catphan500Analyzer`
- DICOM series loader: `load_dicom_series()`
- Single-image loader: `load_image()`

## 4. Recommended Defaults

For most users:

- use DICOM-series mode rather than single-image mode,
- use `full_analysis` unless you specifically need selected modules,
- use `--plot` when checking a new dataset, and
- try `--center-algorithm mirror` when you want the uniformity center to be
   determined by whole-image mirror correlation instead of the default
   edge-based finder, and
- keep the original DICOM files because they provide spacing and timing metadata.

## 5. Where to Go Next

- See `INSTALLATION.md` for the full installation guide.
- See `CLI_USAGE.md` for the full CLI reference.
- See `README.md` for the package overview.
- See `docs/` for the published documentation source.
