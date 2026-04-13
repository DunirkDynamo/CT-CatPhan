<!-- Copilot / agent instructions for the CT-CatPhan repository -->
# CT-CatPhan — Agent Instructions

This file contains concise, actionable notes to help an AI coding agent work productively in this repository.

Overview
- Purpose: a small, modular Python toolkit to analyze CatPhan CT phantom images from DICOM series or single slices.
- Key entry points: `catphan500.Catphan500Analyzer` as the primary orchestrator and CLI entry point `catphan500` (`catphan500.cli:main`).
- Primary mode: DICOM series with automatic slice selection, 3-slice averaging, and rotation detection.
- Legacy mode: Single-image analysis (backwards compatible).

Important files & directories
- `src/catphan500/analysis.py` — `Catphan500Analyzer` exposes `run_<module>()` methods (e.g. `run_uniformity`, `run_high_contrast`, `run_ctp401`, `run_ctp515`).
- `src/catphan500/io.py` — Image I/O functions:
  - `load_image(path)` - loads single DICOM/image file, returns `(image_array, metadata_dict)`
  - `load_dicom_series(folder_path)` - recursively loads all DICOM files from folder, returns list of dicts with images, metadata, timestamps
  - `select_dicom_folder()` - opens GUI dialog for folder selection
  - Uses `force=True` for robust DICOM reading, timestamp-based chronological sorting
- Legacy internal analyzers were removed; current analysis depends primarily on the external `alexandria` module, distributed as the `alexandria-project` package.
  - `UniformityAnalyzer` - 5-ROI uniformity analysis (center, N, E, S, W)
  - `HighContrastAnalyzer` - MTF and line pair resolution analysis
  - `AnalyzerCTP401` - HU linearity with material inserts, includes `detect_rotation()` method for automatic rotation detection
  - `AnalyzerCTP515` - low-contrast detectability (CNR analysis)
  - All implement `analyze()` and populate `self.results` with JSON-serializable dicts
- `src/catphan500/` — primary public package surface.
- `test_scans/` — contains sample DICOMs (`linearity.dcm`, `linepairs.dcm`, `uniformity.dcm`) useful for manual testing.
- `pyproject.toml` — lists runtime dependencies (`numpy`, `scipy`, `pydicom`, `imageio`, `matplotlib`, `scikit-image`, `alexandria-project`).

Architecture & conventions (what to know)
- **Two operation modes**:
  1. **Series mode** (recommended): Pass `dicom_series` from `load_dicom_series()` to `Catphan500Analyzer`. Each module automatically selects its designated slice and applies 3-slice averaging.
  2. **Single-image mode**: Pass single `image` array (backwards compatible, no averaging).
- **Central analyzer pattern**: `Catphan500Analyzer` is the coordinator. It:
  - stores `self.dicom_series` (list of slice dicts) OR `self.image` (single array) and `self.spacing` (pixel spacing)
  - has configurable slice indices: `uniformity_slice_index`, `high_contrast_slice_index`, `ctp401_slice_index`, `ctp515_slice_index`
  - provides `run_<module>()` methods which:
    - load/average appropriate slice(s) from series
    - call corresponding analyzer classes
    - handle rotation detection (ctp401) and propagation (high_contrast, ctp515)
  - stores results in `self.results` (a flat dict) and keeps analyzer objects on underscored attributes: `_uniformity_analyzer`, `_high_contrast_analyzer`, `_ctp401_analyzer`, `_ctp515_analyzer`.
- **Rotation detection workflow**:
  1. `run_ctp401()` detects rotation using air ROI positions (default behavior)
  2. Stores angle in `self.results['rotation_angle']`
  3. Subsequent `run_high_contrast()` and `run_ctp515()` automatically use detected rotation
  4. Manual override: pass `t_offset` or `angle_offset` parameters to `run_*()` methods
- Analyzer contract:
  - Typical method: `.analyze()` -> returns a JSON-serializable `dict` and sets `self.results`.
  - Many analyzers set derived attributes used by plotters (e.g. `.image`, `.center`, `.pixel_spacing`, `.lp_axis`, `.nMTF`). Check the analyzer implementation before using in plotters.
- Plotter contract:
  - Plotting is now driven through analyzer helpers and `alexandria` plotter classes.
  - Plot methods return a `matplotlib.Figure` and do not save files unless code outside calls `fig.savefig()`.

Common pitfalls & repo-specific gotchas
- **Inconsistent coordinate ordering**: some helpers return `(row, col)` while others treat `center` as `(x, y)` or `(cx, cy)`. Before manipulating coordinates, inspect the specific analyzer's code.
- **I/O optional imports**: `io.py` imports `pydicom` and `imageio` inside try/except; missing packages raise `ImportError` when a DICOM or other image is requested. When writing tests or running the CLI, ensure the environment has the required packages.
- **Slice loading in series mode**: When `dicom_series` is provided, `run_*()` methods must explicitly load the appropriate slice (checking `if self.dicom_series is not None`). Forgetting this check causes `NoneType` errors.
- **Rotation detection order**: Run `run_ctp401()` FIRST to enable automatic rotation detection for other modules. If called out of order, rotation won't be available.
- **Slice averaging flag**: `use_slice_averaging` must be set in `__init__` and requires `dicom_series` (not just `image`). Default is `False` for backwards compatibility.
- **Timestamp-based sorting**: DICOM series are sorted by acquisition timestamps in reverse chronological order (newest first). If slices seem wrong, check timestamp debug output from `load_dicom_series()`.
- **Plotters sometimes call `analyzer.analyze()`** inside their constructor — be careful to avoid double-analysis or unwanted side-effects.
- **Plotter expectations**: some plotters expect analyzer attributes or methods that might be missing (e.g. `HighContrastPlotter` expects `to_dict()`, `lpx`, `lp_x`, `lp_y`, `lp_axis`, `nMTF`). Confirm the analyzer exposes those.

Developer workflows / commands
- **Quick manual run (DICOM series, recommended)**:
  - `catphan500 -m full_analysis --plot` (opens folder dialog)
  - `catphan500 path/to/dicom_folder -m uniformity high_contrast ctp401 --plot --save-plot outdir`
- **Legacy single-image mode**:
  - `catphan500 path/to/slice.dcm --single-image -m uniformity --plot`
- **Programmatic use (series mode)**:
  ```python
  from catphan500.io import load_dicom_series
  from catphan500.analysis import Catphan500Analyzer

  series = load_dicom_series('path/to/dicom_folder')
  ana = Catphan500Analyzer(dicom_series=series, use_slice_averaging=True)
  ana.run_ctp401()  # Detects rotation
  ana.run_uniformity()
  ana.run_high_contrast()  # Uses detected rotation
  ana.save_results_json('results.json')
  print(f"Detected rotation: {ana.results['rotation_angle']:.2f}°")
  ```
- **Programmatic use (legacy single image)**:
  ```python
  from catphan500.io import load_image
  from catphan500.analysis import Catphan500Analyzer

  img, meta = load_image('test_scans/uniformity.dcm')
  ana = Catphan500Analyzer(image=img, spacing=meta.get('Spacing'))
  ana.run_uniformity()
  ana.save_results_json('uniformity.json')
  ```
- Use `test_scans/` images for quick visual/manual checks of single-image mode.

Code review hints for agents
- When adding/modifying analyzers, keep the `.analyze()` return value JSON-serializable and place final, user-facing values into `self.results`.
- Maintain `Catphan500Analyzer`'s pattern of exposing per-module analyzers on underscored attributes if plot helpers rely on them.
- **Slice loading in `run_*()` methods**: Always check `if self.dicom_series is not None` and load the appropriate slice before creating analyzer instances.
- **Rotation handling**: If adding new modules that need rotation correction, check for `self.results.get('rotation_angle')` and use it as default offset.
- **Backwards compatibility**: Maintain support for both `dicom_series` and single `image` input modes in `Catphan500Analyzer.__init__()`.
- Avoid changing the public API signatures (`Catphan500Analyzer.__init__`, `run_<module>`, `load_image`, `load_dicom_series`) without updating the CLI mapping in `src/catphan500/cli.py`.
- **Timestamp sorting**: If modifying `load_dicom_series()`, preserve timestamp-based chronological sorting logic.

When to run tests / manual checks
- There are no unit tests in the repository; rely on `test_scans/` for manual verification.
- Validate plotting visually — plotters return figures; use `fig.savefig()` in CI/dev scripts if adding automated visual checks.

Where to look next (for new agents)
- `src/catphan500/analysis.py` for orchestration details and `alexandria` integration.
- `src/catphan500/` for the primary public package surface.
- `src/catphan500/cli.py` for how modules are discovered, how plots are saved, and the JSON output flow.

If anything above is unclear or you want more detail (e.g., automatic tests, stricter API contracts, or examples for a specific analyzer), say which area to expand and I will iterate.
