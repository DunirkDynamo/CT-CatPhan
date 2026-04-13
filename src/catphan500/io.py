"""Image-loading utilities for CT-CatPhan workflows.

This module centralizes the file and folder loading behavior used by the CLI
and programmatic APIs. It supports two main use cases:

1. loading a single image file for direct analysis, and
2. loading a complete DICOM series from a folder tree for orchestrated module
   analysis.

The functions in this module focus on safe ingestion of image data and light
metadata extraction. They do not perform any analysis on the loaded images.
"""

from typing import Tuple, Optional, List, Dict
import numpy as np
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

# Import optional third-party image readers defensively so the user receives a
# clear error only when they request a workflow that actually needs them.
try:
    import pydicom
except Exception:
    pydicom = None

try:
    import imageio
except Exception:
    imageio = None


def _read_dicom(path: str) -> Tuple[np.ndarray, dict]:
    """Read a single DICOM image file from disk.

    Args:
        path (str): Filesystem path to the DICOM file.

    Returns:
        tuple[np.ndarray, dict]: The image array and a metadata dictionary with
            commonly used DICOM fields.

    Raises:
        ImportError: If ``pydicom`` is not installed.
    """
    # DICOM reading requires pydicom; fail with an explicit message if the
    # dependency is not available in the current environment.
    if pydicom is None:
        raise ImportError("pydicom required to read DICOM files. Install with 'pip install pydicom'.")
    ds = pydicom.dcmread(path)  # Parsed DICOM dataset object.
    arr = ds.pixel_array.astype(float)  # Image array normalized to floating point for analysis.
    #if hasattr(ds, "RescaleIntercept") and hasattr(ds, "RescaleSlope"):
     #   arr = arr * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
    # Collect only the fields currently needed by the package's analysis layer.
    meta = {
        "Spacing": getattr(ds, 'PixelSpacing', None),
        "SliceThickness": getattr(ds, 'SliceThickness', None),
        "Modality": getattr(ds, 'Modality', None)
    }
    return arr, meta


def _read_imageio(path: str) -> Tuple[np.ndarray, dict]:
    """Read a non-DICOM image file using ``imageio``.

    Args:
        path (str): Filesystem path to the image file.

    Returns:
        tuple[np.ndarray, dict]: The image array and an empty metadata
            dictionary because non-DICOM files do not carry the same structured
            metadata fields used by this package.

    Raises:
        ImportError: If ``imageio`` is not installed.
    """
    # Non-DICOM image reading requires imageio; fail with an explicit message
    # if that dependency is unavailable.
    if imageio is None:
        raise ImportError("imageio required to read non-DICOM images. Install with 'pip install imageio'.")
    arr = imageio.imread(path)  # Raw image array returned by imageio.

    # Convert RGB-style images into grayscale because the analysis pipeline
    # expects one scalar value per pixel.
    if arr.ndim == 3:
        arr = arr[..., :3]
        arr = 0.299 * arr[..., 0] + 0.587 * arr[..., 1] + 0.114 * arr[..., 2]
    arr = arr.astype(float)  # Normalize image dtype for downstream analysis.
    return arr, {}


def load_image(path: str) -> Tuple[np.ndarray, dict]:
    """
    Load an image file (DICOM or standard image format).

    Automatically detects format based on file extension. DICOM files are
    read with pydicom (with metadata extraction), while other formats use
    imageio. Handles both explicit .dcm/.dicom extensions and DICOM files
    without standard extensions.

    Args:
        path (str): File path to load.

    Returns:
        Tuple[np.ndarray, dict]: Image array and metadata dictionary.
                                Metadata includes 'Spacing', 'SliceThickness',
                                and 'Modality' for DICOM files, empty dict otherwise.

    Raises:
        ImportError: If required package (pydicom or imageio) is not installed.
    """
    # Normalize the filename for extension-based dispatch.
    lower = path.lower()  # Lowercased path string used for extension checks.
    if lower.endswith('.dcm') or lower.endswith('.dicom'):
        return _read_dicom(path)
    
    # Attempt a forced DICOM read even when the filename does not advertise a
    # DICOM extension, because many clinical exports omit conventional suffixes.
    ds = pydicom.dcmread(path, force=True)  # Force-read DICOM dataset from a non-standard filename.
    ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian  # Normalize transfer syntax for pixel access.

    arr = ds.pixel_array.astype(float)  # Image array normalized to floating point.
    #if hasattr(ds, "RescaleIntercept") and hasattr(ds, "RescaleSlope"):
     #   arr = arr * float(ds.RescaleSlope) + float(ds.RescaleIntercept)
    # Collect the metadata fields used by the analysis layer.
    meta = {
        "Spacing": getattr(ds, 'PixelSpacing', None),
        "SliceThickness": getattr(ds, 'SliceThickness', None),
        "Modality": getattr(ds, 'Modality', None)
    }
    return arr, meta
    #return _read_imageio(path)


def select_dicom_folder() -> Optional[str]:
    """Open a GUI folder picker for selecting a DICOM series directory.
    
    Returns:
        str | None: Path to the selected folder, or ``None`` when the user
            cancels the dialog.
    """
    # Create a minimal Tk application solely to host the native folder dialog.
    root = tk.Tk()  # Temporary hidden Tk root window.
    root.withdraw()  # Hide the main window.
    root.attributes('-topmost', True)  # Bring the selection dialog to the foreground.
    
    folder_path = filedialog.askdirectory(  # Folder chosen by the user.
        title="Select DICOM Folder",
        mustexist=True
    )
    
    root.destroy()
    return folder_path if folder_path else None


def load_dicom_series(folder_path: str) -> List[Dict[str, any]]:
    """Load a DICOM series by recursively scanning a folder tree.
    
    Args:
        folder_path (str): Root folder expected to contain DICOM files.
    
    Returns:
        list[dict[str, Any]]: List of dictionaries, each containing:
            - 'image': np.ndarray pixel array
            - 'metadata': dict with Spacing, SliceThickness, Modality
            - 'path': str path to the DICOM file
            - 'instance_number': int slice/instance number (if available)
            - 'timestamp': chronological value used for final series sorting
    
    Raises:
        ImportError: If pydicom is not installed.
        ValueError: If no valid DICOM files found in folder.
    """
    # DICOM series loading requires pydicom because every candidate file is
    # read as a DICOM dataset.
    if pydicom is None:
        raise ImportError("pydicom required to read DICOM files. Install with 'pip install pydicom'.")
    
    folder = Path(folder_path)  # Root directory provided by the caller.
    if not folder.exists():
        raise ValueError(f"Folder does not exist: {folder_path}")
    
    # Walk the directory tree and gather every plausible DICOM candidate. DICOM
    # files often have arbitrary names and may not use a formal extension.
    import os
    dicom_files = []  # Candidate file paths that will be tested as DICOM.
    for root, _, file_list in os.walk(folder_path):
        for filename in file_list:
            # Skip obvious text or directory-index artifacts that are not image
            # payloads and are unlikely to be valid DICOM files.
            if any(x in filename.lower() for x in ['dir', '.txt', '.json', '.md']):
                continue
            dicom_files.append(Path(root, filename))
    
    print(f"Found {len(dicom_files)} potential files to check")
    
    # Attempt to read every candidate file as DICOM and accumulate the ones that
    # successfully expose image data and the metadata needed by the package.
    series = []  # Successfully loaded DICOM slices.
    failed_count = 0  # Count of candidate files that did not parse as usable DICOM.
    for file_path in dicom_files:
        try:
            # Force-read each file for compatibility with non-standard exports.
            ds = pydicom.dcmread(str(file_path), force=True)  # Parsed DICOM dataset object.
            ds.file_meta.TransferSyntaxUID = pydicom.uid.ImplicitVRLittleEndian  # Normalize transfer syntax for pixel access.
            
            arr = ds.pixel_array.astype(float)  # Image array normalized to floating point.
            
            # Extract the available temporal fields so the final series can be
            # sorted in a stable chronological order.
            acquisition_time = getattr(ds, 'AcquisitionTime', None)  # Time-only acquisition field.
            acquisition_datetime = getattr(ds, 'AcquisitionDateTime', None)  # Combined date/time acquisition field.
            series_time = getattr(ds, 'SeriesTime', None)  # Series-level time fallback.
            content_time = getattr(ds, 'ContentTime', None)  # Generic content time fallback.
            
            # Use the first available timestamp field in priority order so the
            # final slice ordering is as meaningful as possible.
            timestamp = acquisition_datetime or acquisition_time or series_time or content_time or '000000.000000'  # Chronological sort key.
            
            # Capture the metadata fields used elsewhere in the package.
            meta = {
                "Spacing": getattr(ds, 'PixelSpacing', None),
                "SliceThickness": getattr(ds, 'SliceThickness', None),
                "Modality": getattr(ds, 'Modality', None),
                "InstanceNumber": getattr(ds, 'InstanceNumber', None),
                "SliceLocation": getattr(ds, 'SliceLocation', None),
                "AcquisitionTime": acquisition_time,
                "AcquisitionDateTime": acquisition_datetime
            }
            
            # Append the successfully loaded slice record to the output series.
            series.append({
                'image': arr,  # Pixel array for the loaded slice.
                'metadata': meta,  # Metadata subset used by the analysis layer.
                'path': str(file_path),  # Original on-disk path for traceability.
                'instance_number': meta.get('InstanceNumber', 0),  # Slice instance identifier when present.
                'timestamp': timestamp  # Sort key used for chronological ordering.
            })
        except Exception as e:
            # Skip files that cannot be parsed as usable DICOM while retaining a
            # small amount of diagnostic output for debugging.
            failed_count += 1  # Increment the count of rejected candidate files.
            if failed_count <= 3:
                print(f"⚠️  Could not read {file_path.name} as DICOM: {e}")
            continue
    
    # Summarize additional failures beyond the first few printed examples.
    if failed_count > 3:
        print(f"⚠️  ({failed_count - 3} more files failed to load)")
    
    # Fail explicitly when the folder walk produced no usable DICOM slices.
    if not series:
        raise ValueError(f"No valid DICOM files found in {folder_path}. Checked {len(dicom_files)} files, all failed.")
    
    # Sort the final series in reverse chronological order so the analyzer sees
    # the same slice ordering each time.
    series.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # Print the resulting slice order so users can verify that the temporal sort
    # produced the expected series layout.
    print(f"\n📊 Slice order (by acquisition time):")
    for idx, slice_data in enumerate(series):
        timestamp = slice_data['timestamp']  # Timestamp used to order this slice.
        path_name = Path(slice_data['path']).name  # Filename shown in the diagnostic output.
        print(f"  [{idx}] {path_name} - Time: {timestamp}")
    
    return series