# Catphan404 CLI Usage Guide

This guide provides examples and explanations for using the Catphan404 command-line interface.

## Installation

Ensure the package and its dependencies are installed:

```bash
pip install -r requirements.txt
```

## Basic Usage

**Recommended (DICOM folder with GUI selection):**
```bash
catphan404 -m <module> [options]
```

**Specify DICOM folder path:**
```bash
catphan404 <folder_path> -m <module> [options]
```

**Legacy single-image mode:**
```bash
catphan404 <image_path> --single-image -m <module> [options]
```

Or if not installed as a package:
```bash
python -m Catphan404.cli [folder_path] -m <module> [options]
```

## Available Modules

- `uniformity`      - Uniformity analysis (CTP486 module)
- `detailed_uniformity` - Concentric profile sampling (CTP486 module)
- `high_contrast`   - High-contrast resolution / line pairs (CTP528 module)
- `ctp401`          - HU linearity / material analysis (CTP401 module)
- `ctp515`          - Low-contrast detectability (CTP515 module)

**Note:** In folder mode, each module automatically selects its corresponding slice and performs 3-slice averaging for improved image quality.

## Common Options

- `-m, --modules`   - **Required.** Specify which module(s) to run
- `-f, --folder`    - Explicitly treat input as DICOM folder (default behavior)
- `--single-image`  - Legacy mode: treat input as single image file (no slice averaging)
- `--out, -o`       - JSON output file path (default: `<module>.json`)
- `--plot`          - Generate diagnostic plots (handled by Catphan404Analyzer)
- `--save-plot`     - Directory or file path to save plots as PNG
- `--show-plot`     - Display plots interactively (default: full_analysis saves without showing)
- `--no-save`       - Skip saving JSON results (useful for quick visual checks)

## Automatic Rotation Detection

**The package automatically detects phantom rotation** using air ROI positions in the CTP401 module and applies corrections to all subsequent modules.

### How It Works

1. **Detection** (CTP401 module): Locates top and bottom air ROIs, calculates rotation angle from their positions
2. **Storage**: Rotation angle stored in results as `rotation_angle` (degrees)
3. **Propagation**: Subsequent modules (`high_contrast`, `ctp515`) automatically use detected rotation
4. **Override**: Manual rotation offsets can be provided via programmatic API

### Workflow Example

**Recommended: Use run_full_analysis() method**

```python
from catphan404.io import load_dicom_series
from catphan404.analysis import Catphan404Analyzer

series = load_dicom_series('scans/catphan')
analyzer = Catphan404Analyzer(dicom_series=series, use_slice_averaging=True)

# Run all modules in proper order (uniformity → detailed_uniformity → ctp401 → high_contrast → ctp515)
results = analyzer.run_full_analysis()

# Or run specific modules
results = analyzer.run_full_analysis(modules=['uniformity', 'detailed_uniformity', 'ctp401'])

print(f"Detected rotation: {results['rotation_angle']:.2f}°")
```

**Advanced: Run individual modules manually**

```python
# For fine-grained control, run modules individually
analyzer.run_uniformity()
analyzer.run_detailed_uniformity()
analyzer.run_ctp401()  # Automatically detects rotation
print(f"Detected rotation: {analyzer.results['rotation_angle']:.2f}°")

# Other modules use detected rotation automatically
analyzer.run_high_contrast()  # Uses rotation_angle from results
analyzer.run_ctp515()  # Uses rotation_angle from results
```

### Manual Override (Programmatic API)

**Note:** Manual rotation control requires calling individual `run_*` methods instead of `run_full_analysis()`.

```python
# Disable automatic detection and set manual rotation
analyzer.run_ctp401(detect_rotation=False, t_offset=2.5)  # 2.5° manual offset

# Or override automatic detection
analyzer.run_ctp401(t_offset=3.0)  # Uses 3.0° instead of detected value

# Apply same offset to other modules
analyzer.run_high_contrast(t_offset=3.0)
analyzer.run_ctp515(angle_offset=3.0)
```

**Note:** The CLI does not expose rotation parameters; use the programmatic API for manual control.

## DICOM Series Loading Details

### Robust File Loading

- **Recursive search**: Searches all subdirectories for DICOM files
- **Extension-agnostic**: Attempts to read ALL files as DICOM, regardless of extension
- **Force mode**: Uses `pydicom.dcmread(path, force=True)` for non-standard DICOM files
- **Timestamp sorting**: Sorts slices chronologically using acquisition timestamps (reverse order)

### Supported Timestamp Fields

 The loader checks these DICOM tags in order:
1. `AcquisitionDateTime`
2. `AcquisitionTime`
3. `SeriesTime`
4. `ContentTime`

Slices are sorted in **reverse chronological order** (newest first), which typically matches the scanner's reconstruction order.

### Debug Output

The `load_dicom_series()` function prints:
- Number of files checked
- Number of successful DICOM loads
- Slice order with timestamps for verification
- First 3 error messages (if any)

## Example Commands

### Using Folder Selection Dialog (Recommended)

Simply run without specifying a path to open a GUI folder selector:

```bash
catphan404 -m uniformity detailed_uniformity high_contrast --plot
```

The program will prompt you to select a DICOM folder, then automatically:
1. Load all DICOM slices from the folder
2. Select the appropriate slice for each module
3. Apply 3-slice averaging
4. Run the analysis

### Specify DICOM Folder Path

```bash
catphan404 path/to/dicom_series -m uniformity detailed_uniformity ctp401 --plot --save-plot results/
```

### Multiple Modules in One Run

Run all available modules on a DICOM series:

```bash
catphan404 scans/catphan_series -m uniformity detailed_uniformity high_contrast ctp401 ctp515 --plot
```

**Or use the full_analysis shortcut:**

```bash
catphan404 -m full_analysis --plot
```

Output:
- `full_analysis.json` (or `uniformity_detailed_uniformity_high_contrast_ctp401_ctp515.json`) with all results
- Plots saved to current directory (but not displayed)

**To display plots interactively:**
```bash
catphan404 -m full_analysis --plot --show-plot
```

### Save All Plots to Directory

**Using full_analysis (saves automatically, doesn't display):**
```bash
catphan404 -m full_analysis --plot --save-plot output_dir/
```

**Or specify individual modules:**
```bash
catphan404 -m uniformity detailed_uniformity high_contrast ctp401 ctp515 --plot --save-plot output_dir/
```

Produces separate PNG files for each module:
- `output_dir/uniformity.png`
- `output_dir/detailed_uniformity.png`
- `output_dir/high_contrast.png`
- `output_dir/ctp401.png`
- `output_dir/ctp515.png`

**Using a file prefix instead of directory:**
```bash
catphan404 -m full_analysis --plot --save-plot qa_jan2026
```

Produces:
- `qa_jan2026_uniformity.png`
- `qa_jan2026_detailed_uniformity.png`
- `qa_jan2026_high_contrast.png`
- `qa_jan2026_ctp401.png`
- `qa_jan2026_ctp515.png`

### Quick Visual Check (Display Only)

View plots interactively without saving:

```bash
catphan404 -m uniformity --plot --show-plot --no-save
```

### Save Plots Without Displaying (full_analysis default)

```bash
catphan404 -m full_analysis --plot
# Saves plots to current directory but doesn't show them
```

### Legacy Single-Image Mode

For backwards compatibility, analyze a single DICOM slice without 3-slice averaging:

```bash
catphan404 path/to/uniformity.dcm --single-image -m uniformity --plot
```

**Note:** Single-image mode is not recommended as it lacks the noise reduction benefits of 3-slice averaging.

### Custom Output File

Specify custom JSON output filename:

```bash
python -m Catphan404.cli image.dcm -m uniformity --out my_results.json
```

## Supported Input Formats

**Primary: DICOM Folder (Recommended)**
- Folder containing multiple DICOM slices
- Requires `pydicom`
- Enables automatic slice selection and 3-slice averaging
- Preserves all metadata (pixel spacing, slice location, etc.)

**Legacy: Single Image Files**
- **DICOM** (`.dcm`) - Single slice, requires `pydicom` and `--single-image` flag
- **PNG, TIFF, JPG** - Supported via `imageio` with `--single-image` flag

**Note:** Single-image mode does not perform slice averaging and may have reduced image quality.

## Programmatic Usage

For scripting or batch processing:

**Using DICOM series (recommended):**
```python
from Catphan404.io import load_dicom_series
from Catphan404.analysis import Catphan404Analyzer

# Load DICOM series from folder
dicom_series = load_dicom_series('path/to/dicom_folder')

# Create analyzer with series
analyzer = Catphan404Analyzer(dicom_series=dicom_series)

# Run multiple modules - each selects its own slice automatically
# IMPORTANT: Run ctp401 first to enable automatic rotation detection
analyzer.run_uniformity()
analyzer.run_ctp401()  # Detects rotation automatically
analyzer.run_high_contrast()  # Uses detected rotation from ctp401
analyzer.run_ctp515()  # Uses detected rotation from ctp401

# Check detected rotation
print(f"Phantom rotation: {analyzer.results.get('rotation_angle', 0):.2f}°")

# Save all results (includes rotation_angle)
analyzer.save_results_json('output.json')

# Generate plots via the analyzer
figs = analyzer.generate_plots(
  modules=['uniformity', 'detailed_uniformity', 'high_contrast'],
  save_plot_path=Path('results'),
  show_plot=False
)

# Or call individual plot helpers
fig1 = analyzer.plot_uniformity()
fig2 = analyzer.plot_detailed_uniformity()
fig3 = analyzer.plot_high_contrast()
fig1.savefig('uniformity.png')
fig2.savefig('detailed_uniformity.png')
fig3.savefig('high_contrast.png')
```

**Legacy single-image mode:**
```python
from Catphan404.io import load_image
from Catphan404.analysis import Catphan404Analyzer

# Load single image
img, meta = load_image('path/to/image.dcm')

# Create analyzer with single image
analyzer = Catphan404Analyzer(image=img, spacing=meta.get('Spacing'))

# Run specific module
analyzer.run_uniformity()

# Save results
analyzer.save_results_json('output.json')
```

## Workflow Example

Complete analysis workflow using DICOM folder:

```bash
# Single command analyzes all modules from one DICOM series
catphan404 scans/catphan_20260122 -m uniformity detailed_uniformity high_contrast ctp401 ctp515 \
  --plot --save-plot results/ --out results/full_analysis.json
```

This automatically:
1. Loads all DICOM slices
2. Selects appropriate slices for each module (slice indices: uniformity=6, high_contrast=2, ctp401=0, ctp515=4)
3. Performs 3-slice averaging for each module
4. Runs all analyses
5. Saves JSON results and plots

**Customizing slice indices:**
```python
from Catphan404.io import load_dicom_series
from Catphan404.analysis import Catphan404Analyzer

dicom_series = load_dicom_series('scans/catphan_20260122')
analyzer = Catphan404Analyzer(dicom_series=dicom_series)

# Customize slice indices if needed
analyzer.uniformity_slice_index = 10
analyzer.high_contrast_slice_index = 5

analyzer.run_uniformity()
analyzer.run_high_contrast()
```

## Output Files

### JSON Results

**When running multiple modules**, all results are saved to a **single JSON file** with each module's data as a separate key.

**Default naming:**
- If no `--out` is specified, the filename is derived from module names
- Example: `uniformity_high_contrast_ctp401.json` or `full_analysis.json`

**Custom filename:**
```bash
catphan404 -m full_analysis --out qa_report_jan2026.json
```

**JSON structure for multiple modules:**
```json
{
  "uniformity": {
    "centre": {"mean": 5.2, "std": 3.1},
    "north": {"mean": 5.5, "std": 3.0},
    "east": {"mean": 5.3, "std": 3.2},
    "south": {"mean": 5.4, "std": 3.1},
    "west": {"mean": 5.1, "std": 3.0},
    "uniformity": 1.23
  },
  "center": [256.0, 256.0],
  "rotation_angle": 2.34,
  "high_contrast": {
    "mtf_50": 0.85,
    "resolution_lp_per_mm": 2.5
  },
  "ctp401": {
    "air": {"mean": -998.5, "std": 10.2},
    "ldpe": {"mean": -95.3, "std": 8.1}
  },
  "ctp515": {
    "n_detected": 6,
    "blobs": {...}
  }
}
```

**Note:** `rotation_angle` (in degrees) is added when `run_ctp401()` is executed with automatic detection enabled (default).

### Plot Images

**When running multiple modules**, each module generates a **separate PNG file**.

**Behavior based on `--save-plot` argument:**

1. **Directory path** - Saves each module as `<dir>/<module>.png`:
   ```bash
   catphan404 -m full_analysis --plot --save-plot Results/
   ```
   Creates: `Results/uniformity.png`, `Results/high_contrast.png`, etc.

2. **File prefix** - Saves as `<prefix>_<module>.png`:
   ```bash
   catphan404 -m full_analysis --plot --save-plot monthly_qa.png
   ```
   Creates: `monthly_qa_uniformity.png`, `monthly_qa_high_contrast.png`, etc.

3. **Omitted** - Plots displayed but not saved:
   ```bash
   catphan404 -m full_analysis --plot
   ```
   Plots appear on screen only.

**Each PNG file contains the full visualization** for its module (ROI overlays, graphs, histograms, profiles, etc.).

### Single Module Output Examples

**Single module example:**
```json
{
  "uniformity": {
    "centre": {"mean": 5.2, "std": 3.1},
    "north": {"mean": 5.5, "std": 3.0},
    ...
    "uniformity": 1.23
  },
  "center": [256.0, 256.0]
}
```

**ctp515.json:**
```json
{
  "ctp515": {
    "n_detected": 6,
    "blobs": {
      "roi_15mm": {
        "x": 250, "y": 180,
        "mean": -35.2, "std": 4.1,
        "cnr": 8.5, "contrast": -2.3
      },
      ...
    }
  }
}
```

### Plot Files

PNG images showing:
- **Uniformity:** Image with ROIs, histograms, error bars, boxplots, profiles
- **High Contrast:** Image with segments, MTF curve, stacked line profiles
- **CTP401:** Image with ROIs, per-ROI histograms, heatmaps
- **CTP515:** Image with color-coded ROIs, CNR/Contrast plots, statistics table

## Troubleshooting

### Module Not Found Error

If you see `ModuleNotFoundError`, ensure you're running from the repository root:

```bash
cd c:\GitHub\catphan404
python -m Catphan404.cli ...
```

### Missing Dependencies

Install required packages:

```bash
pip install numpy scipy matplotlib pydicom imageio scikit-image
```

### DICOM Loading Issues

If DICOM files fail to load, ensure `pydicom` is installed:

```bash
pip install pydicom
```

### Wrong Module for Image

Each phantom slice should use its corresponding module:
- Uniformity slice → `uniformity`
- Line pair slice → `high_contrast`
- Material inserts → `ctp401`
- Low-contrast discs → `ctp515`

Running the wrong module will produce incorrect or meaningless results.

### DICOM Files Not Loading

If DICOM files are not detected:
1. Verify files are valid DICOM (even without `.dcm` extension)
2. Check error messages printed by `load_dicom_series()` (shows first 3 errors)
3. Ensure `pydicom` is installed: `pip install pydicom`
4. Try loading individual files with `pydicom.dcmread(path, force=True)`

### Incorrect Slice Order

If slices appear in wrong order:
1. Check debug output from `load_dicom_series()` - shows timestamps
2. Verify DICOM files have acquisition timestamps (`AcquisitionTime`, `AcquisitionDateTime`, etc.)
3. If timestamps are missing, manually sort by `InstanceNumber` or `SliceLocation`

### Rotation Detection Issues

If rotation appears incorrect:
1. Run `ctp401` module first to enable detection
2. Check `rotation_angle` in results JSON
3. Manually override if needed: `ana.run_ctp401(t_offset=<angle>)`
4. Verify CTP401 slice is correctly loaded (should show material inserts)
5. Disable detection if phantom is perfectly aligned: `detect_rotation=False`

## Tips

1. **Use folder mode** with DICOM series for best results (automatic slice selection + 3-slice averaging)
2. **Run ctp401 first** to enable automatic rotation detection for all subsequent modules
3. **Always use `--plot`** when first analyzing a new dataset to visually verify results
4. **Run multiple modules** in one command to save time: `-m uniformity high_contrast ctp401 ctp515`
5. **Check `rotation_angle`** in JSON output to verify phantom alignment
6. **Verify slice order** - check debug output from `load_dicom_series()` if results seem incorrect
7. **Check JSON output** for quantitative metrics and QA records
8. **Organize output directories** by scan date or phantom serial number
9. **Verify slice indices** if using a non-standard phantom orientation (adjust via programmatic API)
10. **Keep original DICOM files** as they contain critical metadata (pixel spacing, slice location, timestamps, etc.)

## Getting Help

View CLI help:

```bash
python -m Catphan404.cli --help
```

For more information, see:
- `README.md` - Package overview
- `.github/copilot-instructions.md` - Developer guidance
- Source code in `Catphan404/` directory
