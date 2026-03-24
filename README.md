# -----------------------------
# File: README.md
# -----------------------------
# Catphan 404 Analysis

A modular Python package for analyzing Catphan 404 CT phantom DICOM series.
Supports automatic slice selection, 3-slice averaging, automatic rotation detection, and comprehensive QA analysis.

## Features

- **Automatic Rotation Detection**: Detects phantom rotation using air ROI positions in CTP401 module, automatically applies correction to all subsequent modules
- **3-Slice Averaging**: Improves image quality by averaging target slice with neighbors, reducing noise
- **Timestamp-Based Slice Ordering**: Automatically sorts DICOM slices chronologically for correct sequence
- **Robust DICOM Loading**: Recursively searches directories and reads files regardless of extension using `force=True`
- **Multi-Slice Series Support**: Load entire DICOM series with automatic per-module slice selection
- **Modular Architecture**: Run individual QA modules or complete analysis workflows
- **CLI + Programmatic API**: Use via command-line or Python scripts

## Quick Start

**CLI (Recommended):**
```bash
# Open folder selection dialog - saves plots to current directory
catphan404 -m full_analysis --plot

# Display plots interactively
catphan404 -m full_analysis --plot --show-plot

# Or specify folder path and output directory
catphan404 path/to/dicom_folder -m uniformity detailed_uniformity high_contrast --plot --save-plot results/
```

**Programmatic Usage:**
```python
from catphan404.io import load_dicom_series
from catphan404.analysis import Catphan404Analyzer

# Load DICOM series
series = load_dicom_series('path/to/dicom_folder')

# Create analyzer with 3-slice averaging
analyzer = Catphan404Analyzer(dicom_series=series, use_slice_averaging=True)

# Recommended: Use run_full_analysis() for complete workflow
results = analyzer.run_full_analysis()  # Runs all modules in proper order

# Or run specific modules only
results = analyzer.run_full_analysis(modules=['uniformity', 'detailed_uniformity', 'ctp401'])

# Access results
print(f"Detected rotation: {results['rotation_angle']:.2f}°")
print(f"Uniformity: {results['uniformity']['uniformity']:.2f}%")

# Advanced: Run individual modules for fine-grained control
analyzer.run_uniformity()
analyzer.run_detailed_uniformity()
analyzer.run_ctp401()  # Detects rotation, stores in analyzer.results['rotation_angle']
analyzer.run_high_contrast()  # Automatically uses detected rotation
analyzer.run_ctp515()  # Automatically uses detected rotation

# Manual rotation override (requires individual module calls)
analyzer.run_ctp401(t_offset=2.5)  # Manually set 2.5° rotation
analyzer.run_high_contrast(t_offset=2.5)
analyzer.run_ctp515(angle_offset=2.5)

# Disable automatic rotation detection
analyzer.run_ctp401(detect_rotation=False, t_offset=0.0)

# Save results
analyzer.save_results_json('results.json')

# Optional: generate plots after analysis
analyzer.generate_plots(
    modules=['uniformity', 'high_contrast', 'ctp401', 'ctp515'],
    save_plot_path='results',
    show_plot=False
)
```

**Legacy Single-Image Mode:**
```python
from catphan404.io import load_image
from catphan404.analysis import Catphan404Analyzer

img, meta = load_image('slice.dcm')
ana = Catphan404Analyzer(image=img, spacing=meta.get('Spacing'))
ana.run_uniformity()
```

**Using Individual Analyzers Directly:**

You can use any analyzer module independently without `Catphan404Analyzer`:

```python
from alexandria import UniformityAnalyzer
from catphan404.io import load_image
import numpy as np

# Load image
img, meta = load_image('test_scans/uniformity.dcm')

# Estimate phantom center
threshold = np.percentile(img, 75)
mask = img > threshold
coords = np.argwhere(mask)
cy, cx = coords.mean(axis=0)

# Get pixel spacing
spacing = meta.get('Spacing', [1.0, 1.0])
pixel_spacing = float(spacing[0])

# Use analyzer directly
analyzer = UniformityAnalyzer(
    image=img,
    center=(cx, cy),
    pixel_spacing=pixel_spacing
)

results = analyzer.analyze()
print(results)
```

All analyzer modules follow the same pattern and are provided by the **Alexandria** library:
- `UniformityAnalyzer(image, center, pixel_spacing)`
- `HighContrastAnalyzer(image, center, pixel_spacing)`
- `CTP401Analyzer(image, center, pixel_spacing)`
- `CTP515Analyzer(image, center, pixel_spacing)`

## Requirements
- numpy
- scipy
- pydicom (for DICOM files)
- imageio (for TIFF/JPG/PNG formats)
- scikit-image (for image processing)
- matplotlib (for plotting)
- **alexandria** (shared CatPhan analysis library)

## Documentation
You can generate HTML docs using Sphinx:
```bash
sphinx-quickstart
make html
```

