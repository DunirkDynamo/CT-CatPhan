# CT-CatPhan CLI Usage Guide

This guide documents the current public command-line behavior for the
`catphan500` entry point.

## Installation

Install the package from the repository root:

```bash
python -m pip install -e .
```

The backend dependency is installed from the `alexandria-project` distribution
and imported by CT-CatPhan as `alexandria`.

For fuller install instructions, see `INSTALLATION.md`.

## Command Forms

Open the GUI folder picker and run one or more modules:

```bash
catphan500 -m <module> [options]
```

Pass a DICOM folder path explicitly:

```bash
catphan500 <folder_path> -m <module> [options]
```

Run the legacy single-image mode:

```bash
catphan500 <image_path> --single-image -m <module> [options]
```

Run the module directly after editable installation:

```bash
python -m catphan500.cli [folder_path] -m <module> [options]
```

## Modules

- `uniformity`: Uniformity analysis on the CTP486 slice.
- `detailed_uniformity`: Concentric profile sampling on the uniformity slice.
- `ctp401`: HU linearity and material insert analysis.
- `high_contrast`: High-contrast resolution and line-pair analysis.
- `ctp515`: Low-contrast detectability analysis.
- `full_analysis`: Convenience alias that expands to the dependency-aware order `uniformity -> detailed_uniformity -> ctp401 -> high_contrast -> ctp515`.

## Core Options

- `-m`, `--modules`: Required list of modules to run.
- `-f`, `--folder`: Explicitly treat the input as a DICOM folder.
- `--single-image`: Treat the input path as one image instead of a DICOM series.
- `--average-slices`: Enable 3-slice averaging in DICOM-series mode.
- `-o`, `--out`: JSON output path.
- `--no-save`: Skip JSON file generation.
- `--plot`: Generate diagnostic plots.
- `--save-plot`: Save plots to an existing directory or use the value as a filename prefix.
- `--show-plot`: Display plots interactively.

## Recommended Usage Patterns

Run a full DICOM-series analysis with the folder picker:

```bash
catphan500 -m full_analysis --plot
```

Current behavior in this mode:

- the folder picker opens if no path is supplied,
- the full dependency-aware analysis order is used,
- JSON output is written to `uniformity_detailed_uniformity_ctp401_high_contrast_ctp515.json` unless `--out` is supplied,
- plots are generated, and
- because `full_analysis` was requested, plots are saved to the current directory by default even when `--save-plot` is omitted.

Run a full analysis against a known DICOM folder and save results to explicit locations:

```bash
catphan500 scans/catphan_series -m full_analysis --plot --save-plot results --out results/full_analysis.json
```

Run only selected modules:

```bash
catphan500 scans/catphan_series -m uniformity detailed_uniformity ctp401
```

Display plots without saving JSON:

```bash
catphan500 scans/catphan_series -m uniformity --plot --show-plot --no-save
```

Legacy single-image invocation:

```bash
catphan500 slice.dcm --single-image -m uniformity --plot
```

## DICOM-Series Workflow

Folder mode is the primary workflow. In this mode the CLI:

1. Recursively scans the provided directory for candidate DICOM files.
2. Loads slices with `pydicom.dcmread(..., force=True)`.
3. Sorts slices using acquisition-related timestamps.
4. Builds a `Catphan500Analyzer` around the loaded series.
5. Runs the requested modules in a dependency-aware order.

When `--average-slices` is enabled, module-specific target slices are averaged
with neighboring slices where available.

## Rotation Detection

Rotation detection is handled by the `ctp401` workflow.

- `run_ctp401()` estimates a rotation angle from air ROI geometry.
- The detected value is stored in results as `rotation_angle`.
- Later module runs can reuse that angle automatically.

For CLI usage, rotation behavior is automatic. Manual angle overrides are only
available through the Python API.

## Output Behavior

### JSON Results

Results from all requested modules are written into one JSON file. If `--out` is
not specified, the filename is derived from the final module list actually run.

Examples:

- `uniformity.json`
- `uniformity_ctp401.json`
- `uniformity_detailed_uniformity_ctp401_high_contrast_ctp515.json`

The JSON payload can include shared top-level fields such as:

- `center`
- `rotation_angle`
- per-module result dictionaries such as `uniformity`, `ctp401`, `high_contrast`, and `ctp515`

### Plot Files

When `--plot` is used, each module produces a separate figure.

If `--save-plot` points to an existing directory, files are written as:

```bash
catphan500 -m full_analysis --plot --save-plot results
```

Typical files produced:

- `results/uniformity.png`
- `results/detailed_uniformity.png`
- `results/ctp401.png`
- `results/high_contrast.png`
- `results/ctp515.png`

If `--save-plot` is not an existing directory, it is treated as a filename prefix:

```bash
catphan500 -m full_analysis --plot --save-plot monthly_qa
```

Typical files produced:

- `monthly_qa_uniformity.png`
- `monthly_qa_detailed_uniformity.png`
- `monthly_qa_ctp401.png`
- `monthly_qa_high_contrast.png`
- `monthly_qa_ctp515.png`

If `full_analysis` is requested with `--plot` and `--save-plot` is omitted, the
CLI defaults to saving plots in the current working directory.

## Python API Notes

The CLI is a thin orchestration layer over the Python API. The equivalent
programmatic workflow is:

```python
from pathlib import Path
from catphan500 import Catphan500Analyzer, load_dicom_series

series = load_dicom_series("path/to/dicom_folder")
analyzer = Catphan500Analyzer(dicom_series=series, use_slice_averaging=True)

results = analyzer.run_full_analysis()
analyzer.save_results_json("results.json")
analyzer.generate_plots(save_plot_path=Path("results"), show_plot=False)
```

If you want manual control over rotation handling or module order, call the
individual `run_*` methods directly.

## Troubleshooting

### `alexandria` Import Errors

If the environment reports that `alexandria` cannot be imported, reinstall the
package and its dependencies:

```bash
python -m pip install -e .
```

The install dependency is named `alexandria-project`, even though the import
name used by CT-CatPhan is `alexandria`.

### DICOM Files Not Loading

If folder loading fails:

1. Confirm the folder actually contains valid DICOM slices.
2. Check the first reported parse errors printed by `load_dicom_series()`.
3. Verify `pydicom` is installed in the active environment.

### Unexpected Analysis Results

Make sure the requested module matches the slice content:

- `uniformity` for the uniformity slice
- `ctp401` for the material insert slice
- `high_contrast` for the line-pair slice
- `ctp515` for the low-contrast slice

Running the wrong module on the wrong slice can still succeed technically while
producing meaningless QA values.

If slices appear in the wrong order:

1. Check the debug output from `load_dicom_series()`.
2. Verify the DICOM files contain acquisition-related timestamps.
3. Confirm the input folder is the intended scan series.

### Rotation Detection Issues

If rotation appears incorrect:

1. Make sure the CTP401 slice is part of the requested workflow.
2. Check `rotation_angle` in the results JSON.
3. Verify the selected slice actually contains the material inserts.
4. Use the Python API if you need manual override parameters such as `t_offset` or `angle_offset`.

## Tips

1. Use folder mode with DICOM series for the intended workflow.
2. Use `full_analysis` when you want the package to handle dependency ordering automatically.
3. Use `--plot` when first checking a new dataset so you can visually verify the module outputs.
4. Use `--average-slices` in series mode when you want the optional 3-slice averaging behavior.
5. Check the generated JSON output for `rotation_angle` and module-level QA metrics.
6. Keep the original DICOM files because they contain the metadata used for spacing and slice ordering.

## Getting Help

View CLI help:

```bash
catphan500 --help
```

For more information, see:

- `README.md` for the package overview.
- `INSTALLATION.md` for installation guidance.
- `docs/` for the published documentation source.
- `src/catphan500/` for the package implementation.
