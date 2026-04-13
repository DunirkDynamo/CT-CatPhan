# -----------------------------
# File: README.md
# -----------------------------
# CT-CatPhan

CT-CatPhan is a Python toolkit for CatPhan CT phantom QA workflows. The public
package and CLI surface is `catphan500`, with `Catphan500Analyzer` acting as the
main orchestration layer for multi-module analysis, result export, and plotting.

The package is designed primarily for DICOM series workflows and supports:

- automatic per-module slice selection,
- optional 3-slice averaging,
- automatic rotation detection from the CTP401 slice,
- JSON-serializable results, and
- CLI and programmatic usage.

The numerical analysis backend is distributed on PyPI as `alexandria-project`
and imported in Python as `alexandria`.

## Package Structure

```text
CT-CatPhan/
|-- scripts/
|   |-- build_executable.bat     # Windows batch wrapper for the build
|   `-- build_executable.ps1     # Repeatable PowerShell build helper
|-- packaging/
|   `-- pyinstaller/
|       `-- CT-CatPhan.spec      # Checked-in PyInstaller build spec
|-- src/
|   `-- catphan500/
|       |-- __init__.py      # Public package exports
|       |-- analysis.py      # Main orchestration layer and plot helpers
|       |-- cli.py           # Command-line entry point
|       `-- io.py            # Image and DICOM loading utilities
|-- docs/                    # Sphinx source for GitHub Pages
|-- README.md                # Repository overview
|-- QUICK_START.md           # Fast onboarding for users and developers
|-- INSTALLATION.md          # Installation and environment setup
|-- BUILD_EXECUTABLES.md     # Windows executable build guide
`-- CLI_USAGE.md             # CLI reference and examples
```

At a high level, `cli.py` and the public package exports feed into
`Catphan500Analyzer` in `analysis.py`, which uses `io.py` for data loading and
delegates numerical analysis to the external `alexandria` backend.

## Installation

Install the package in editable mode from the repository root:

```powershell
python -m pip install -e .
```

This installs CT-CatPhan plus its runtime dependencies, including
`alexandria-project`.

For the full installation guide, environment notes, verification steps, and
docs setup, see `INSTALLATION.md`.

## Quick Start

### CLI

Run a full analysis with the folder picker:

```powershell
catphan500 -m full_analysis --plot
```

Run against a known DICOM folder and save plots to a directory:

```powershell
catphan500 C:\path\to\dicom_folder -m full_analysis --plot --save-plot results
```

Run selected modules only:

```powershell
catphan500 C:\path\to\dicom_folder -m uniformity detailed_uniformity ctp401
```

### GUI Launcher

Launch the simple folder-picker workflow:

```powershell
catphan500-gui
```

The launcher asks for the input DICOM folder and then an output folder. It
runs the full analysis and saves both the JSON report and plot PNG files into
the chosen output location.

### Python API

Recommended DICOM-series workflow:

```python
from catphan500 import Catphan500Analyzer, load_dicom_series

series = load_dicom_series(r"C:\path\to\dicom_folder")
analyzer = Catphan500Analyzer(dicom_series=series, use_slice_averaging=True)

results = analyzer.run_full_analysis()
analyzer.save_results_json("results.json")

print(f"Rotation: {results['rotation_angle']:.2f} degrees")
print(f"Uniformity: {results['uniformity']['uniformity']:.2f}%")
```

Legacy single-image workflow:

```python
from catphan500 import Catphan500Analyzer, load_image

image, metadata = load_image("slice.dcm")
analyzer = Catphan500Analyzer(image=image, spacing=metadata.get("Spacing"))
analyzer.run_uniformity()
```

## Public API

Package-level exports:

- `Catphan500Analyzer`
- `load_image(path)`
- `load_dicom_series(folder_path)`
- `select_dicom_folder()`

Main analyzer methods:

- `run_full_analysis(modules=None)`
- `run_uniformity()`
- `run_detailed_uniformity()`
- `run_ctp401()`
- `run_high_contrast()`
- `run_ctp515()`
- `save_results_json(path)`
- `generate_plots(...)`

Plot helper methods are also exposed on the analyzer for module-specific figure
generation.

## Recommended Workflow

For most users, the intended path is:

1. Load a DICOM series.
2. Instantiate `Catphan500Analyzer` with that series.
3. Run `run_full_analysis()` or an ordered subset of modules.
4. Save JSON results.
5. Generate plots when visual QA output is needed.

If you call modules individually, run `run_ctp401()` before `run_high_contrast()`
or `run_ctp515()` when you want automatic rotation correction to propagate.

## Analysis Modules

- `uniformity`: Uniformity analysis for the CTP486 slice.
- `detailed_uniformity`: Concentric radial/profile sampling on the uniformity slice.
- `ctp401`: Material insert and HU linearity analysis, plus rotation detection.
- `high_contrast`: High-contrast line-pair analysis.
- `ctp515`: Low-contrast detectability analysis.
- `full_analysis`: CLI shortcut that expands to the dependency-aware full module order.

## DICOM Series Behavior

When a folder is loaded with `load_dicom_series()`:

- the folder tree is searched recursively,
- candidate files are read with `pydicom.dcmread(..., force=True)`,
- slices are sorted using acquisition-related timestamps, and
- each loaded slice record includes the image array, metadata, path, instance number, and timestamp.

This is the preferred operating mode because it preserves module-specific slice
selection and enables optional 3-slice averaging.

## Development Notes

- Source code lives under `src/catphan500/`.
- The console entry point is `catphan500 = "catphan500.cli:main"`.
- The project depends on Alexandria analyzers and plotters provided by the
    `alexandria-project` distribution.

## Releases

The repository uses automatic versioning from git tags through `setuptools-scm`.
To publish a release, create and push a tag in the format `vX.Y.Z`.

Example:

```powershell
git tag v1.2.3
git push origin v1.2.3
```

Pushing a matching tag triggers GitHub Actions to:

1. publish the documentation site to GitHub Pages
2. build the Windows executable
3. create or update the GitHub Release
4. upload a versioned asset such as `CT-CatPhan-v1.2.3.exe`

Standard branch pushes and merges do not publish docs or create release assets.

## Related Docs

- See `QUICK_START.md` for the shortest path to first use or first development setup.
- See `INSTALLATION.md` for full installation, verification, and docs-build instructions.
- See `BUILD_EXECUTABLES.md` for the Windows executable build workflow.
- See `CLI_USAGE.md` for command-line examples and option details.
- See `docs/CHANGELOG.md` for the project changelog in GitHub-renderable Markdown.
- See `docs/` for the Sphinx documentation source published to GitHub Pages.

## Building Docs

The published documentation source lives in the repository-root `docs/`
directory and is built with Sphinx autodocumentation.

Install the docs dependencies and build the site locally:

```powershell
python -m pip install -e .[docs]
python -m sphinx -b html docs docs/_build/html
```

The generated site will be written to `docs/_build/html`.

