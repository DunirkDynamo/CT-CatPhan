# Changelog

This page consolidates the repository's historical development notes into one
publishable changelog for the documentation site.

## 2026-04-13

### Repository documentation overhaul

- Expanded in-code documentation across the active `catphan500` package,
  including the analyzer, CLI, I/O, and package initializer modules.
- Reworked the top-level `README.md` to present the package as the current
  stable public surface rather than a rename-in-progress.
- Added and refined repo-root user documentation:

  - `INSTALLATION.md`
  - `QUICK_START.md`
  - `CLI_USAGE.md`

- Added a package-structure diagram to the root `README.md` and the published
  docs overview page.

### GitHub Pages and docs publishing

- Added a root-level `docs/` Sphinx site configured for autodocumentation.
- Added GitHub Pages workflow configuration for automated docs publishing.
- Switched the changelog to Markdown so it renders cleanly on GitHub while
  remaining part of the published docs site.
- Configured the docs site to publish repo-root Markdown documents through
  wrapper pages so GitHub and GitHub Pages share one canonical source.

### Repository cleanup

- Removed the obsolete `requirements.txt` file and standardized dependency
  guidance around `pyproject.toml`.
- Consolidated the historical daylogs into the changelog and removed the old
  `daylogs/` directory.

## 2026-02-23

- Updated `Catphan500Analyzer` to own plot generation directly through
  `generate_plots()` and per-module plot helper methods.
- Simplified the CLI plotting flow so plotting behavior is coordinated through
  the analyzer rather than split across separate orchestration layers.

## 2026-01-23

### I/O and DICOM loading

- Updated DICOM series loading to recurse through directories with `os.walk()`
  and attempt DICOM reads regardless of file extension.
- Added `force=True` during DICOM reads for compatibility with non-standard
  exports.
- Normalized transfer syntax handling with `ImplicitVRLittleEndian`
  assignment where needed.
- Added timestamp-based slice sorting using acquisition-related DICOM fields.
- Improved load diagnostics by reporting file counts, initial errors, and final
  slice order information.

### Analysis workflow and bug fixes

- Fixed slice loading so each `run_*()` method correctly pulls images from a
  DICOM series even when slice averaging is disabled.
- Improved spacing fallback behavior in `run_uniformity()`.
- Corrected coordinate ordering issues in `run_high_contrast()` and
  `run_ctp401()`.
- Improved phantom center estimation by changing the thresholding strategy used
  during center detection.
- Changed the default `run_ctp515()` crop values to remove unwanted default
  cropping.

### Rotation detection integration

- Added automatic phantom rotation detection to the CTP401 workflow using air
  ROI geometry.
- Stored detected rotation in `results['rotation_angle']`.
- Propagated detected rotation automatically into high-contrast and low-
  contrast workflows.
- Preserved manual override support through explicit rotation parameters.

### CLI and documentation

- Added `--show-plot` to the CLI.
- Changed `full_analysis --plot` behavior so plots save by default without
  blocking interactive execution.
- Updated repository documentation to explain the revised plotting workflow.

## 2026-01-20

### Series-mode support

- Added GUI folder selection through `select_dicom_folder()`.
- Added recursive DICOM-series loading through `load_dicom_series()`.
- Extended `Catphan500Analyzer` to accept a DICOM series while preserving the
  legacy single-image path.
- Added configurable slice indices for the main analysis modules.
- Added the `_average_slices()` helper for three-slice averaging.
- Updated the main `run_*()` module methods to operate against the selected
  series slice.

### Packaging updates

- Removed the unnecessary `pathlib` dependency from package requirements.
- Added the missing `scikit-image` dependency required by image-processing
  code paths.

### Architecture impact

- Established the two supported operating modes used throughout the current
  package design:

  - legacy single-image analysis, and
  - DICOM-series analysis with automatic slice selection and optional
    averaging.