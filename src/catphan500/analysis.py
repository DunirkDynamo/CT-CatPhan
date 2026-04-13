"""Core analysis orchestration for the CT-CatPhan package.

This module provides the main high-level analyzer used by the package. The
intent of this file is not to implement the lower-level CatPhan algorithms
directly. Instead, it coordinates image selection, optional slice averaging,
execution order, result collection, and plot generation while delegating the
actual quantitative work to analyzers and plotters supplied by the
``alexandria`` backend.

The primary public object defined here is :class:`Catphan500Analyzer`. It is
designed to support two modes of operation:

1. DICOM-series mode, where the analyzer selects the correct slice for each
    CatPhan module and can optionally average neighboring slices.
2. Single-image mode, where one already-loaded 2D image is analyzed directly.

The class stores JSON-serializable results for downstream reporting and keeps
references to backend analyzer instances so that plot objects can be created
after analysis has completed.
"""

from typing import Optional, Tuple, Dict, Any
import numpy as np
import json
from matplotlib import pyplot as plt
from pathlib import Path


# Import the analysis backend eagerly because this repository treats the
# backend as a normal installation dependency rather than an optional plugin.
try:
    from alexandria import (
        UniformityAnalyzer,
        HighContrastAnalyzer,
        CTP401Analyzer,
        CTP515Analyzer,
        DetailedUniformityAnalyzer,
    )
    from alexandria.plotters.high_contrast_plotter import HighContrastPlotter
    from alexandria.plotters.uniformity_plotter import UniformityPlotter
    from alexandria.plotters.ctp401_plotter import CTP401Plotter
    from alexandria.plotters.ctp515_plotter import CTP515Plotter
    from alexandria.plotters.detailed_uniformity_plotter import DetailedUniformityPlotter
except ImportError as exc:
    raise ImportError(
        "catphan500 requires the distribution package 'alexandria-project', "
        "which provides the importable 'alexandria' module used for analyzers "
        "and plotters."
    ) from exc


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that converts numpy-specific values into plain Python types.

    The analysis backend returns a mixture of built-in Python values and numpy
    containers/scalars. Standard ``json`` serialization does not understand
    numpy arrays or numpy scalar dtypes, so this encoder normalizes those
    values before they are written to disk.
    """

    def default(self, obj):
        """Convert numpy-specific values into JSON-compatible representations.

        Args:
            obj (Any): The object that the standard JSON encoder could not
                serialize directly.

        Returns:
            Any: A Python-native representation suitable for JSON encoding.
        """
        # Convert numpy arrays into nested Python lists so their contents can
        # be emitted as JSON arrays.
        if isinstance(obj, np.ndarray):
            return obj.tolist()

        # Convert numpy integer scalar types into built-in ``int`` values.
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)

        # Convert numpy floating scalar types into built-in ``float`` values.
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)

        # Fall back to the parent implementation for everything else.
        return super().default(obj)


class Catphan500Analyzer:
    """
    Central coordinator for CT-CatPhan phantom analysis workflows.

    This class is the main public API for users who want a single object to
    manage CatPhan analysis end to end. It owns the currently selected image,
    pixel spacing, execution settings, module-specific slice indices, plot-ready
    analyzer references, and the cumulative results dictionary.

    The class deliberately separates orchestration concerns from numerical
    analysis concerns. Backend analyzer classes from ``alexandria`` compute the
    actual metrics, while this coordinator decides:

    - which slice to load for a requested module,
    - whether neighboring slices should be averaged,
    - when a previously detected rotation angle should be reused,
    - where results should be stored for later serialization, and
    - how module plots should be generated after analysis has completed.

    Attributes:
        dicom_series (list | None): Full DICOM series produced by
            ``load_dicom_series()`` when operating in folder mode.
        image (np.ndarray | None): The currently active 2D image for the module
            being analyzed, or the single-image input in legacy mode.
        spacing (tuple[float, float] | None): Pixel spacing for the currently
            active image, stored as ``(row_spacing_mm, col_spacing_mm)``.
        use_slice_averaging (bool): Flag indicating whether the target slice
            should be averaged with its immediate neighbors.
        uniformity_slice_index (int): Series index used for the uniformity
            module when operating in DICOM-series mode.
        high_contrast_slice_index (int): Series index used for the high-contrast
            module when operating in DICOM-series mode.
        ctp401_slice_index (int): Series index used for the CTP401 module.
        ctp515_slice_index (int): Series index used for the CTP515 module.
        catphan_diameter_mm (float): Reference CatPhan diameter stored for
            center-detection related configuration and future use.
        center_threshold (float): Primary threshold forwarded to backend module
            analyzers for phantom-center localization.
        center_threshold_fallback (float): Secondary threshold used when the
            primary threshold cannot establish a stable phantom center.
        results (dict[str, Any]): JSON-serializable results accumulated from
            each executed module.
    """

    def __init__(self, dicom_series=None, image: np.ndarray = None, spacing: Optional[Tuple[float, float]] = None, use_slice_averaging: bool = False, catphan_diameter_mm: float = 150.0, center_threshold: float = -980.0, center_threshold_fallback: float = -900.0):
        """Initialize the analyzer with either a DICOM series or one image.

        Args:
            dicom_series (list | None): The full DICOM series returned by
                ``load_dicom_series()``. Each entry is expected to contain an
                image array and metadata dictionary.
            image (np.ndarray | None): Single 2D image for direct analysis when
                DICOM-series orchestration is not being used.
            spacing (tuple[float, float] | None): Pixel spacing associated with
                ``image`` when operating in single-image mode.
            use_slice_averaging (bool): Whether module methods should average a
                target slice with its immediate neighbors in DICOM-series mode.
            catphan_diameter_mm (float): Reference CatPhan diameter retained as
                analyzer configuration for center-finding related workflows.
            center_threshold (float): Primary threshold passed to backend
                analyzers during phantom-center localization.
            center_threshold_fallback (float): Fallback threshold passed to
                backend analyzers when the primary threshold is insufficient.

        Raises:
            ValueError: If neither ``dicom_series`` nor ``image`` is provided.

        Notes:
            Either series mode or single-image mode must be selected.
            Slice averaging only has meaning in series mode.
        """
        # The analyzer cannot function without some source image data.
        if dicom_series is None and image is None:
            raise ValueError("Either dicom_series or image must be provided")
        
        # Persist the full DICOM series when the caller is using folder mode.
        self.dicom_series = dicom_series  # Full list of DICOM slice records.
        
        # Enable slice averaging only when the user requested it and a true
        # multi-slice DICOM series is actually available.
        self.use_slice_averaging = use_slice_averaging and (dicom_series is not None)  # Series-only option.
        
        # Support direct analysis of a single image for backwards compatibility
        # and ad hoc workflows that do not begin from a full DICOM series.
        if image is not None:
            self.image = np.array(image, dtype=float)  # Active image used by module methods.
            self.spacing = (float(spacing[0]), float(spacing[1])) if spacing else None  # Pixel spacing for the active image.
        else:
            # In series mode, these values are populated lazily by each module
            # method after the appropriate slice has been selected.
            self.image = None  # Active image placeholder until a slice is selected.
            self.spacing = None  # Active spacing placeholder until metadata is loaded.
        
        # Store the default slice indices used by each analysis module when
        # operating on a DICOM series. These values are configurable so callers
        # can override them when their scan geometry differs.
        self.uniformity_slice_index = 6  # Default series index for the CTP486 slice.
        self.high_contrast_slice_index = 2  # Default series index for the CTP528 slice.
        self.ctp401_slice_index = 0  # Default series index for the CTP401 slice.
        self.ctp515_slice_index = 4  # Default series index for the CTP515 slice.
        
        # Preserve center-finding related configuration on the analyzer so all
        # module methods forward the same backend tuning values.
        self.catphan_diameter_mm = catphan_diameter_mm  # Reference phantom diameter.
        self.center_threshold = center_threshold  # Primary center-detection threshold.
        self.center_threshold_fallback = center_threshold_fallback  # Backup threshold if the primary one fails.

        # Store all module outputs in one JSON-friendly dictionary so callers
        # can save a single structured report after any subset of analyses.
        self.results: Dict[str, Any] = {}  # Aggregated analysis results keyed by module name.

        # Keep references to backend analyzer objects after they run so plot
        # helper methods can generate figures from the most recent analysis.
        self._uniformity_analyzer = None  # Backend analyzer for CTP486 summary analysis.
        self._detailed_uniformity_analyzer = None  # Backend analyzer for concentric profile analysis.
        self._high_contrast_analyzer = None  # Backend analyzer for CTP528 spatial resolution.
        self._ctp401_analyzer = None  # Backend analyzer for CTP401 material inserts.
        self._ctp515_analyzer = None  # Backend analyzer for CTP515 low-contrast targets.

    # ------------------ Existing uniformity / CT-number ------------------
    def run_uniformity(self):
        """
        Run the CTP486 uniformity analysis workflow.

        This method selects the configured uniformity slice, resolves its pixel
        spacing, constructs the backend uniformity analyzer, executes the
        backend analysis, and stores the resulting summary in ``self.results``.

        Populates:
            self.results['uniformity']: ROI statistics and the final uniformity
                metric returned by the backend analyzer.

        Notes:
            The backend analyzer is responsible for center and boundary
            detection. This coordinator is responsible for selecting the input
            image and forwarding consistent configuration.
        """
        # In series mode, replace the current active image with the configured
        # uniformity slice or a 3-slice average centered on that slice.
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.uniformity_slice_index)
            else:
                slice_data = self.dicom_series[self.uniformity_slice_index]  # Selected DICOM record for CTP486.
                self.image = slice_data['image']  # Image array fed into the backend analyzer.
                spacing_raw = slice_data['metadata'].get('Spacing')  # Raw spacing metadata from the selected slice.
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None  # Normalized spacing tuple.
        
        # Use the first spacing value as the backend pixel spacing scalar and
        # fall back to 1.0 mm/pixel if spacing metadata is absent.
        spacing = self.spacing[0] if self.spacing else 1.0  # Scalar spacing forwarded to the backend analyzer.
        
        # Create the backend analyzer with no explicit center so the backend can
        # determine the phantom center using its own logic.
        analyzer = UniformityAnalyzer(
            self.image,
            center=None,
            pixel_spacing=spacing,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        # Execute the backend analysis and store the JSON-serializable result.
        self.results['uniformity'] = analyzer.analyze()  # Final CTP486 summary metrics.

        # Persist the analyzer instance for any follow-on plotting requests.
        self._uniformity_analyzer = analyzer  # Most recent uniformity backend object.

    def run_detailed_uniformity(self):
        """
        Run the detailed CTP486 concentric-profile analysis workflow.

        This method intentionally reuses the uniformity slice index so the
        detailed radial-profile view and the standard uniformity summary refer
        to the same source image.

        Populates:
            self.results['detailed_uniformity']: Detailed concentric-profile
                statistics returned by the backend analyzer.
        """
        # Select the same source image used by the standard uniformity module so
        # both outputs are directly comparable.
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.uniformity_slice_index)
            else:
                slice_data = self.dicom_series[self.uniformity_slice_index]  # Selected DICOM record for detailed uniformity.
                self.image = slice_data['image']  # Image array used for the profile analysis.
                spacing_raw = slice_data['metadata'].get('Spacing')  # Raw pixel spacing from DICOM metadata.
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None  # Normalized spacing tuple.

        # Reduce the spacing tuple to the scalar spacing value expected by the
        # backend analyzer.
        spacing = self.spacing[0] if self.spacing else 1.0  # Scalar backend spacing.

        # Construct the backend analyzer and allow it to perform its own center
        # localization from the provided image.
        analyzer = DetailedUniformityAnalyzer(
            image=self.image,
            center=None,
            pixel_spacing=spacing,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        # Store both the JSON result and the analyzer object for later plotting.
        self.results['detailed_uniformity'] = analyzer.analyze()  # Detailed radial-profile metrics.
        self._detailed_uniformity_analyzer = analyzer  # Most recent detailed-uniformity backend object.


    # ------------------ High Contrast Module (Line pairs) ----------------
    def run_high_contrast(self, t_offset: float = None):
        """
        Run the CTP528 high-contrast spatial-resolution workflow.

        This method selects the configured high-contrast slice, applies any
        available rotation correction, forwards the image into the backend MTF
        analyzer, and stores the resulting resolution metrics.

        Args:
            t_offset (float | None): Manual rotation offset in degrees. When
                omitted, the method reuses ``self.results['rotation_angle']`` if
                that value was produced earlier by ``run_ctp401()``.

        Populates:
            self.results['high_contrast']: MTF curve data, normalized MTF values,
                and summary spatial-resolution metrics from the backend.
        """
        # Select the source image for the high-contrast module. In series mode,
        # this may be either one slice or a 3-slice average around that slice.
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.high_contrast_slice_index)
            else:
                slice_data = self.dicom_series[self.high_contrast_slice_index]  # Selected DICOM record for CTP528.
                self.image = slice_data['image']  # Image array used for line-pair analysis.
                spacing_raw = slice_data['metadata'].get('Spacing')  # Raw spacing metadata from the DICOM slice.
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None  # Normalized spacing tuple.

        # Reuse a previously detected rotation angle unless the caller supplied
        # an explicit manual override for this run.
        if t_offset is None and 'rotation_angle' in self.results:
            t_offset = self.results['rotation_angle']
            print(f"📐 Using detected rotation angle: {t_offset:.2f}° for high contrast")
        elif t_offset is None:
            t_offset = 0

        # Reduce the spacing tuple to the scalar spacing expected by the
        # backend analyzer.
        spacing = self.spacing[0] if self.spacing else 1.0  # Scalar backend spacing.
        
        # Create the backend analyzer and let it compute its own phantom center
        # and other internal geometry.
        analyzer = HighContrastAnalyzer(
            image=self.image,
            center=None,
            pixel_spacing=spacing,
            t_offset_deg=t_offset,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        # Execute the backend analysis and retain the returned metrics.
        res = analyzer.analyze()  # High-contrast spatial-resolution result payload.
        self.results['high_contrast'] = res  # Stored under the module-specific result key.

        # Persist the analyzer instance so plot helpers can render the MTF view.
        self._high_contrast_analyzer = analyzer  # Most recent high-contrast backend object.

    # --------------  Linearity Module (HU material inserts) --------------
    def run_ctp401(self, t_offset: float = None, detect_rotation: bool = True):
        """
        Run the CTP401 material-linearity and rotation-detection workflow.

        This method selects the configured CTP401 slice, constructs the backend
        analyzer, optionally asks the backend to estimate the phantom rotation,
        and stores both the final CTP401 metrics and the chosen rotation angle.

        Args:
            t_offset (float | None): Manual rotation offset in degrees. When
                omitted and ``detect_rotation`` is ``True``, the backend will be
                asked to compute the rotation angle automatically.
            detect_rotation (bool): Flag controlling whether automatic rotation
                detection should run when ``t_offset`` is not provided.

        Populates:
            self.results['ctp401']: Material ROI statistics, linearity values,
                and any calibration-related outputs returned by the backend.
            self.results['rotation_angle']: The detected or user-supplied
                rotation angle used for downstream modules.
        """
        # Select the correct source image for CTP401 analysis. In series mode,
        # this can be either one exact slice or a local 3-slice average.
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.ctp401_slice_index)
            else:
                slice_data = self.dicom_series[self.ctp401_slice_index]  # Selected DICOM record for CTP401.
                self.image = slice_data['image']  # Image array used for insert analysis.
                spacing_raw = slice_data['metadata'].get('Spacing')  # Raw spacing metadata from the selected slice.
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None  # Normalized spacing tuple.

        # Convert the spacing tuple into the scalar spacing value expected by
        # the backend analyzer.
        spacing = self.spacing[0] if self.spacing else 1.0  # Scalar backend spacing.
        
        # Create the backend analyzer and allow it to determine center/boundary
        # details from the provided image.
        analyzer = CTP401Analyzer(
            image=self.image,
            center=None,
            pixel_spacing=spacing,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        # Decide how the rotation angle should be established for this module.
        # Automatic detection is only used when the caller did not supply one.
        if t_offset is None and detect_rotation:
            rotation_angle = analyzer.detect_rotation()  # Backend-estimated phantom rotation angle.
            t_offset = rotation_angle  # Persist the detected value for this analysis call.
            self.results['rotation_angle'] = float(rotation_angle)  # Stored for downstream module reuse.
            print(f"🔄 Detected rotation: {rotation_angle:.2f}°")
        elif t_offset is not None:
            self.results['rotation_angle'] = float(t_offset)  # Explicit user-supplied rotation override.

        # Execute the backend analysis using either the detected angle, the
        # user-supplied angle, or zero degrees if no rotation is available.
        res = analyzer.analyze(t_offset=t_offset if t_offset is not None else 0, verbose=True)  # Final CTP401 result payload.
        self.results['ctp401'] = res  # Stored under the module-specific result key.

        # Persist the analyzer object for later CTP401 plot generation.
        self._ctp401_analyzer = analyzer  # Most recent CTP401 backend object.

    # ------------------ As yet undeveloped modules ---------------- 

    def run_ctp515(self, crop_x=0, crop_y=0, angle_offset: float = None):
        """
        Run the CTP515 low-contrast detectability workflow.

        This method selects the configured low-contrast slice, optionally crops
        it before analysis, applies rotation information from CTP401 when
        available, and stores the resulting detectability metrics.

        Args:
            crop_x (int): Number of pixels to remove from both the left and the
                right edges before the backend analyzer is created.
            crop_y (int): Number of pixels to remove from both the top and the
                bottom edges before the backend analyzer is created.
            angle_offset (float | None): Manual rotation angle in degrees. When
                omitted, the method reuses ``self.results['rotation_angle']`` if
                that value is available.

        Populates:
            self.results['ctp515']: Low-contrast ROI statistics, contrast values,
                and CNR-style detectability metrics returned by the backend.
        """
        # Select the source image for the low-contrast module. In series mode,
        # this may be either the exact target slice or its local average.
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.ctp515_slice_index)
            else:
                slice_data = self.dicom_series[self.ctp515_slice_index]  # Selected DICOM record for CTP515.
                self.image = slice_data['image']  # Image array used for low-contrast analysis.
                spacing_raw = slice_data['metadata'].get('Spacing')  # Raw spacing metadata from the selected slice.
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None  # Normalized spacing tuple.
        
        # Apply symmetric cropping if the caller wants to focus the backend on a
        # smaller central image region.
        if crop_x > 0 or crop_y > 0:
            h, w = self.image.shape  # Original image height and width in pixels.
            cropped_image = self.image[crop_y:h-crop_y, crop_x:w-crop_x]  # Cropped image array passed to the backend.
        else:
            cropped_image = self.image  # Unmodified image array when cropping is not requested.

        # Reuse the CTP401 rotation result unless the caller explicitly provided
        # a low-contrast-specific angle override.
        if angle_offset is None:
            angle_offset = self.results.get('rotation_angle', 0.0)  # Rotation angle reused from CTP401 when available.
            if 'rotation_angle' in self.results:
                print(f"📐 Using detected rotation angle: {angle_offset:.2f}° for CTP515")

        # Convert the spacing tuple into the scalar spacing value expected by
        # the backend analyzer.
        spacing = self.spacing[0] if self.spacing else 1.0  # Scalar backend spacing.
        
        # Create the backend analyzer and allow it to estimate any geometric
        # values it needs from the cropped or uncropped image.
        analyzer = CTP515Analyzer(
            cropped_image,
            center=None,
            pixel_spacing=spacing,
            angle_offset=angle_offset,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )
        
        # Execute the backend analysis and store the returned detectability
        # metrics in the aggregate result dictionary.
        res = analyzer.analyze()  # Final CTP515 result payload.
        self.results['ctp515'] = res  # Stored under the module-specific result key.

        # Persist the analyzer object so the low-contrast plot can be generated.
        self._ctp515_analyzer = analyzer  # Most recent CTP515 backend object.


    # ------------------ Helper functions ------------------
    def _average_slices(self, slice_index: int) -> Tuple[np.ndarray, Optional[Tuple[float, float]]]:
        """
        Average a target slice with its immediate neighbors.

        This helper is used to reduce noise when operating in DICOM-series mode.
        It averages the requested slice with the slice immediately before and the
        slice immediately after it whenever those neighbors exist.
        
        Args:
            slice_index (int): Index of the center slice around which the local
                3-slice average should be computed.
        
        Returns:
            tuple[np.ndarray, tuple[float, float] | None]: A two-item tuple
                containing the averaged image array and the spacing metadata from
                the center slice.
        
        Raises:
            ValueError: If no DICOM series is loaded or the requested index lies
                outside the bounds of the current series.
        """
        # This helper only makes sense when the analyzer owns a full DICOM
        # series; otherwise there are no neighboring slices to average.
        if self.dicom_series is None:
            raise ValueError("Cannot average slices: no DICOM series loaded")
        
        # Reject invalid slice indices before attempting list access.
        if slice_index < 0 or slice_index >= len(self.dicom_series):
            raise ValueError(f"Slice index {slice_index} out of range (0-{len(self.dicom_series)-1})")
        
        # Clamp the averaging window to the valid bounds of the series so edge
        # slices can still be averaged with whatever neighbors exist.
        start_idx = max(0, slice_index - 1)  # First slice index included in the averaging window.
        end_idx = min(len(self.dicom_series) - 1, slice_index + 1)  # Last slice index included in the averaging window.
        
        # Collect each image participating in the local averaging window.
        images_to_average = []  # List of image arrays that will be stacked and averaged.
        for idx in range(start_idx, end_idx + 1):
            images_to_average.append(self.dicom_series[idx]['image'])
        
        # Compute the mean image across all available slices in the window.
        averaged_image = np.mean(images_to_average, axis=0)  # Noise-reduced image array.
        
        # Preserve spacing from the center slice because that metadata should be
        # authoritative for the averaged image.
        center_metadata = self.dicom_series[slice_index]['metadata']  # Metadata from the requested center slice.
        spacing_raw = center_metadata.get('Spacing')  # Raw spacing metadata extracted from the center slice.
        spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None  # Normalized spacing tuple.
        
        return averaged_image, spacing
    

    def save_results_json(self, path):
        """
        Serialize the currently accumulated analysis results to JSON.

        Args:
            path (str | Path): Filesystem path where the JSON report should be
                written.

        Returns:
            Path: The resolved output path object used for the write operation.

        Raises:
            ValueError: If no analysis results exist yet.
            OSError: If writing the file fails.
        """
        # Prevent callers from writing empty reports when no module has run.
        if not self.results:
            raise ValueError(
                "No results available. Run at least one analysis module before saving."
            )

        out_path = Path(path)  # Normalized filesystem path for the JSON report.

        # Ensure the destination directory exists before opening the file.
        if out_path.parent != Path('.'):
            out_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the aggregated results using the custom encoder so numpy values
        # are converted into JSON-compatible Python values.
        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, cls=NumpyEncoder)
        except OSError as e:
            raise OSError(f"Failed to write JSON to {out_path}: {e}")

        return out_path

    def run_full_analysis(self, modules=None):
        """
        Run a coordinated multi-module analysis workflow.

        This convenience method ensures that modules run in an order that keeps
        shared state consistent. In particular, the CTP401 module should run
        before the high-contrast and low-contrast modules when automatic
        rotation reuse is desired.
        
        Args:
            modules (list[str] | None): Optional subset of module names to run.
                If omitted, the full default module sequence is executed.
                
        Returns:
            dict[str, Any]: The aggregate ``self.results`` dictionary after all
                requested modules have completed.
            
        Example:
            >>> analyzer = Catphan500Analyzer(dicom_series=series)
            >>> results = analyzer.run_full_analysis()
            >>> results = analyzer.run_full_analysis(modules=['uniformity', 'ctp401'])
        """
        # Use the full default workflow when the caller does not request a
        # custom subset of modules.
        if modules is None:
            modules = ['uniformity', 'detailed_uniformity', 'ctp401', 'high_contrast', 'ctp515']
        
        # Reorder the user-supplied module list into the dependency-aware order
        # expected by the analysis workflow.
        ordered_modules = []  # Final execution order after dependency normalization.
        if 'uniformity' in modules:
            ordered_modules.append('uniformity')
        if 'detailed_uniformity' in modules:
            ordered_modules.append('detailed_uniformity')
        if 'ctp401' in modules:
            ordered_modules.append('ctp401')
        if 'high_contrast' in modules:
            ordered_modules.append('high_contrast')
        if 'ctp515' in modules:
            ordered_modules.append('ctp515')
        
        # Execute each requested module by resolving and calling its matching
        # ``run_<module>()`` method on this analyzer instance.
        for module_name in ordered_modules:
            run_method = f'run_{module_name}'  # Name of the bound instance method for this module.
            if hasattr(self, run_method):
                getattr(self, run_method)()
                print(f"✅ Completed: {module_name}")
            else:
                print(f"⚠️  Method '{run_method}' not found. Skipping.")
        
        return self.results

    def plot_uniformity(self):
        """Create the uniformity figure for the most recent uniformity run.

        Returns:
            matplotlib.figure.Figure: Figure generated by the backend plotter.

        Raises:
            ValueError: If uniformity analysis has not been executed yet.
        """
        if self._uniformity_analyzer is None:
            raise ValueError("Uniformity analyzer not initialized. Run run_uniformity first.")
        return UniformityPlotter(self._uniformity_analyzer).plot()

    def plot_detailed_uniformity(self):
        """Create the detailed uniformity figure for the most recent run.

        Returns:
            matplotlib.figure.Figure: Figure generated by the backend plotter.

        Raises:
            ValueError: If detailed uniformity analysis has not been executed.
        """
        if self._detailed_uniformity_analyzer is None:
            raise ValueError("Detailed uniformity analyzer not initialized. Run run_detailed_uniformity first.")
        return DetailedUniformityPlotter(self._detailed_uniformity_analyzer).plot()

    def plot_high_contrast(self):
        """Create the high-contrast figure for the most recent run.

        Returns:
            matplotlib.figure.Figure: Figure generated by the backend plotter.

        Raises:
            ValueError: If high-contrast analysis has not been executed.
        """
        if self._high_contrast_analyzer is None:
            raise ValueError("High contrast analyzer not initialized. Run run_high_contrast first.")
        return HighContrastPlotter(self._high_contrast_analyzer).plot()

    def plot_ctp401(self):
        """Create the CTP401 figure for the most recent run.

        Returns:
            matplotlib.figure.Figure: Figure generated by the backend plotter.

        Raises:
            ValueError: If CTP401 analysis has not been executed.
        """
        if self._ctp401_analyzer is None:
            raise ValueError("CTP401 analyzer not initialized. Run run_ctp401 first.")
        return CTP401Plotter(self._ctp401_analyzer).plot()

    def plot_ctp515(self):
        """Create the CTP515 figure for the most recent run.

        Returns:
            matplotlib.figure.Figure: Figure generated by the backend plotter.

        Raises:
            ValueError: If CTP515 analysis has not been executed.
        """
        if self._ctp515_analyzer is None:
            raise ValueError("CTP515 analyzer not initialized. Run run_ctp515 first.")
        return CTP515Plotter(self._ctp515_analyzer).plot()

    def generate_plots(self, modules=None, save_plot_path: Optional[Path] = None, show_plot: bool = False):
        """
        Generate and optionally save plots for one or more analyzed modules.

        Args:
            modules (list[str] | None): Modules to render. If omitted, all known
                plot-capable modules are rendered.
            save_plot_path (Path | None): Directory path or filename prefix used
                when saving plots to disk.
            show_plot (bool): Whether the figures should be displayed
                interactively instead of immediately closed.

        Returns:
            dict[str, matplotlib.figure.Figure]: Mapping from module name to the
                generated matplotlib figure object.
        """
        # Map module names to the helper methods that know how to build the
        # corresponding plot once analysis has already been completed.
        plotters = {
            'uniformity': self.plot_uniformity,
            'detailed_uniformity': self.plot_detailed_uniformity,
            'high_contrast': self.plot_high_contrast,
            'ctp401': self.plot_ctp401,
            'ctp515': self.plot_ctp515
        }

        # Default to plotting every supported module when no explicit subset is
        # requested.
        if modules is None:
            modules = ['uniformity', 'detailed_uniformity', 'high_contrast', 'ctp401', 'ctp515']

        figures = {}  # Mapping from module name to the generated matplotlib figure.
        for module in modules:
            plot_func = plotters.get(module)  # Bound helper used to generate this module's figure.
            if plot_func is None:
                raise ValueError(f"No plotter available for module '{module}'")

            fig = plot_func()  # Fresh matplotlib figure for the requested module.
            figures[module] = fig  # Retain the generated figure in the return mapping.

            # Save the figure when the caller supplied a directory path or a file
            # prefix that should be expanded into module-specific filenames.
            if save_plot_path is not None:
                if save_plot_path.is_dir():
                    target_path = save_plot_path / f"{module}.png"  # Directory mode output path.
                else:
                    suffix = save_plot_path.suffix if save_plot_path.suffix else ".png"  # Default PNG suffix when no extension is given.
                    target_path = save_plot_path.with_name(save_plot_path.stem + f"_{module}" + suffix)  # Prefix mode output path.
                fig.savefig(target_path)

            # Either display the figure interactively or close it immediately to
            # avoid accumulating open matplotlib state in batch workflows.
            if show_plot:
                plt.show()
            else:
                plt.close(fig)

        return figures

    @classmethod
    def run_full_analysis_from_test_data(cls):
        """
        Run the full workflow against a local ``test_scans`` directory.

        This class method is intended for quick smoke testing and developer
        debugging when representative CatPhan DICOM files live beside the
        package source.
        
        Returns:
            Catphan500Analyzer | None: Configured analyzer instance after the
                full workflow completes, or ``None`` if test data is unavailable.
        """
        from .io import load_dicom_series
        import os
        
        # Resolve the expected local test-data directory relative to this
        # module file.
        test_dir = os.path.join(os.path.dirname(__file__), 'test_scans')  # Expected on-disk location for developer smoke-test data.
        if not os.path.exists(test_dir):
            print(f"Test directory not found: {test_dir}")
            print("Run from the catphan500 package directory to use test data.")
            return None
        
        print(f"Loading test data from: {test_dir}")
        series = load_dicom_series(test_dir)  # DICOM series loaded from the developer test directory.
        
        if not series:
            print("No DICOM files found in test_scans/")
            return None
        
        print(f"✅ Loaded {len(series)} DICOM slices")
        
        # Create an analyzer configured for the loaded series and run the full
        # default workflow with slice averaging enabled.
        analyzer = cls(dicom_series=series, use_slice_averaging=True)  # Analyzer instance used for the smoke test.
        print("\n=== Running full analysis ===")
        analyzer.run_full_analysis()
        
        # Print a lightweight human-readable summary of the smoke-test result.
        print(f"\n✓ Center detected: {analyzer.results.get('center')}")
        print(f"✓ Rotation detected: {analyzer.results.get('rotation_angle', 'N/A')}°")
        print(f"✓ Uniformity: {analyzer.results.get('uniformity', {}).get('uniformity', 'N/A')}%")
        print("\nTest complete!")
        
        return analyzer


if __name__ == "__main__":
    # Quick test with sample data
    Catphan500Analyzer.run_full_analysis_from_test_data()