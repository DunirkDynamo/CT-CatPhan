"""Public package surface for CT-CatPhan.

This initializer intentionally re-exports the primary analyzer class and the
core image-loading helpers so users can access the common package entry points
from one import location.
"""

from .analysis import Catphan500Analyzer
from .io import load_image, load_dicom_series, select_dicom_folder

# Declare the supported public exports for the package-level namespace.
__all__ = [
    "Catphan500Analyzer",
    "load_image",
    "load_dicom_series",
    "select_dicom_folder",
]