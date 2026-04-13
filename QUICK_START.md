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

Or run against a known DICOM folder:

```powershell
catphan500 C:\path\to\dicom_folder -m full_analysis --plot --save-plot results
```

What this does:

- loads the DICOM series,
- runs the full module workflow,
- writes a JSON results file, and
- generates per-module plots.

If you only want a few modules:

```powershell
catphan500 C:\path\to\dicom_folder -m uniformity detailed_uniformity ctp401
```

### Path B: Use the Python API

If you want to script the analysis in Python:

```python
from catphan500 import Catphan500Analyzer, load_dicom_series

series = load_dicom_series(r"C:\path\to\dicom_folder")
analyzer = Catphan500Analyzer(dicom_series=series, use_slice_averaging=True)

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
- keep the original DICOM files because they provide spacing and timing metadata.

## 5. Where to Go Next

- See `INSTALLATION.md` for the full installation guide.
- See `CLI_USAGE.md` for the full CLI reference.
- See `README.md` for the package overview.
- See `docs/` for the published documentation source.
