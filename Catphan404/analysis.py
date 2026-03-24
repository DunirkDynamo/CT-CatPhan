from typing import Optional, Tuple, Dict, Any
import numpy as np
import json
from alexandria import UniformityAnalyzer, HighContrastAnalyzer, CTP401Analyzer, CTP515Analyzer, DetailedUniformityAnalyzer
from alexandria.plotters.high_contrast_plotter import HighContrastPlotter
from alexandria.plotters.uniformity_plotter import UniformityPlotter
from alexandria.plotters.ctp401_plotter import CTP401Plotter
from alexandria.plotters.ctp515_plotter import CTP515Plotter
from alexandria.plotters.detailed_uniformity_plotter import DetailedUniformityPlotter
from matplotlib import pyplot as plt
from pathlib import Path


class NumpyEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy types."""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        return super().default(obj)


class Catphan404Analyzer:
    """
    Central coordinator for Catphan 404 phantom analysis.

    Orchestrates analysis of individual phantom modules (uniformity, high-contrast,
    linearity, low-contrast) on DICOM series. Each module is run via
    a dedicated run_* method that selects the appropriate slice, initializes
    the analyzer, executes analysis, and stores results.

    Attributes:
        dicom_series (list): List of DICOM slice dictionaries from load_dicom_series().
        image (np.ndarray): Currently selected 2D CT image (for backwards compatibility).
        spacing (Optional[Tuple[float, float]]): Pixel spacing (x, y) in mm.
        results (dict): Dictionary storing JSON-compatible results from each module.
    """

    def __init__(self, dicom_series=None, image: np.ndarray = None, spacing: Optional[Tuple[float, float]] = None, use_slice_averaging: bool = False, catphan_diameter_mm: float = 150.0, center_threshold: float = -980.0, center_threshold_fallback: float = -900.0):
        """Initialize analyzer with DICOM series or single image.
        
        Args:
            dicom_series (list, optional): List of DICOM dictionaries from load_dicom_series().
            image (np.ndarray, optional): Single 2D image (for backwards compatibility).
            spacing (Optional[Tuple[float, float]], optional): Pixel spacing in mm.
            use_slice_averaging (bool, optional): Enable 3-slice averaging. Default False.
            catphan_diameter_mm (float): Known CatPhan phantom diameter in mm (default: 150mm).
            center_threshold (float): Threshold used by module center finding (default: -980).
            center_threshold_fallback (float): Fallback threshold if the primary fails (default: -900).
        
        Note:
            Either dicom_series or image must be provided.
            Slice averaging requires dicom_series to be provided.
        """
        if dicom_series is None and image is None:
            raise ValueError("Either dicom_series or image must be provided")
        
        # Store the DICOM series
        self.dicom_series = dicom_series
        
        # Determine if we should use slice averaging
        # Only enabled if explicitly requested AND DICOM series is available
        self.use_slice_averaging = use_slice_averaging and (dicom_series is not None)
        
        # For backwards compatibility, support single image input
        if image is not None:
            self.image   = np.array(image, dtype=float)
            self.spacing = (float(spacing[0]), float(spacing[1])) if spacing else None
        else:
            # Will be set when a specific slice is selected
            self.image   = None
            self.spacing = None
        
        # Slice indices for each analysis module (hardcoded defaults)
        # Only used when use_slice_averaging is True
        self.uniformity_slice_index    = 6
        self.high_contrast_slice_index = 2
        self.ctp401_slice_index        = 0
        self.ctp515_slice_index        = 4
        
        # Known phantom diameter for center optimization
        self.catphan_diameter_mm = catphan_diameter_mm

        # Default center threshold for module analyzers
        self.center_threshold = center_threshold
        self.center_threshold_fallback = center_threshold_fallback
        
        self.results: Dict[str, Any] = {}

        # Store actual analyzer objects for plotting:
        self._uniformity_analyzer          = None
        self._detailed_uniformity_analyzer = None
        self._high_contrast_analyzer       = None
        self._ctp401_analyzer              = None
        self._ctp515_analyzer              = None

    # ------------------ Existing uniformity / CT-number ------------------
    def run_uniformity(self):
        """
        Run uniformity analysis (CTP486 module).

        Detects phantom center and boundary, creates UniformityAnalyzer instance,
        analyzes five ROIs, and stores results. Also stores the detected
        center and boundary for use by other modules and plotters.

        Populates:
            self.results['uniformity']: ROI statistics and uniformity metric.
            self.results['center']: Detected (x, y) center coordinates.
            self.results['boundary']: Phantom boundary coordinates for plotting.
        """
        # Get image from DICOM series if available
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.uniformity_slice_index)
            else:
                # Select single slice without averaging
                slice_data = self.dicom_series[self.uniformity_slice_index]
                self.image = slice_data['image']
                spacing_raw = slice_data['metadata'].get('Spacing')
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None
        
        # Get pixel spacing (default to 1.0 if not available)
        spacing = self.spacing[0] if self.spacing else 1.0
        
        # Initialize the uniformity analyzer - it will compute its own center and boundary
        analyzer = UniformityAnalyzer(
            self.image,
            center=None,
            pixel_spacing=spacing,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        # Run analysis and store results
        self.results['uniformity'] = analyzer.analyze()

        # Store the analyzer:
        self._uniformity_analyzer = analyzer

    def run_detailed_uniformity(self):
        """
        Run detailed uniformity analysis using concentric profiles.

        Uses the same slice and spacing as uniformity to keep results aligned.

        Populates:
            self.results['detailed_uniformity']: Detailed profile statistics.
        """
        # Get image from DICOM series if available
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.uniformity_slice_index)
            else:
                slice_data = self.dicom_series[self.uniformity_slice_index]
                self.image = slice_data['image']
                spacing_raw = slice_data['metadata'].get('Spacing')
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None

        spacing = self.spacing[0] if self.spacing else 1.0

        analyzer = DetailedUniformityAnalyzer(
            image=self.image,
            center=None,
            pixel_spacing=spacing,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        self.results['detailed_uniformity'] = analyzer.analyze()
        self._detailed_uniformity_analyzer = analyzer


    # ------------------ High Contrast Module (Line pairs) ----------------
    def run_high_contrast(self, t_offset: float = None):
        """
        Run high-contrast line pair analysis (CTP528 module).

        Analyzes spatial resolution by measuring MTF from line pair patterns.
        Uses center from uniformity analysis if available, otherwise estimates it.
        Will use rotation angle from CTP401 if available.

        Args:
            t_offset (float, optional): Manual rotation offset in degrees.
                                       If None, uses rotation_angle from results.

        Populates:
            self.results['high_contrast']: MTF curve data and resolution metrics.
        """
        # Get image from DICOM series if available
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.high_contrast_slice_index)
            else:
                # Select single slice without averaging
                slice_data = self.dicom_series[self.high_contrast_slice_index]
                self.image = slice_data['image']
                spacing_raw = slice_data['metadata'].get('Spacing')
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None

        # Use detected rotation angle if available and t_offset not provided
        if t_offset is None and 'rotation_angle' in self.results:
            t_offset = self.results['rotation_angle']
            print(f"📐 Using detected rotation angle: {t_offset:.2f}° for high contrast")
        elif t_offset is None:
            t_offset = 0

        spacing = self.spacing[0] if self.spacing else 1.0
        
        # Initialize analyzer - it will compute its own center and boundary
        analyzer = HighContrastAnalyzer(
            image=self.image,
            center=None,
            pixel_spacing=spacing,
            t_offset_deg=t_offset,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        # Store the results of the analysis:
        res = analyzer.analyze()
        self.results['high_contrast'] = res

        # Store the analyzer:
        self._high_contrast_analyzer = analyzer

    # --------------  Linearity Module (HU material inserts) --------------
    def run_ctp401(self, t_offset: float = None, detect_rotation: bool = True):
        """
        Run linearity/scaling analysis (CTP401 module).

        Analyzes material insert ROIs to measure HU values for different
        materials (LDPE, Air, Teflon, Acrylic) and derives a calibration scale.
        Can automatically detect phantom rotation using air ROI positions.

        Args:
            t_offset (float, optional): Rotational offset in degrees for ROI positioning.
                                       If None and detect_rotation=True, will auto-detect.
            detect_rotation (bool): Whether to automatically detect rotation (default True).

        Populates:
            self.results['ctp401']: Material ROI statistics and calibration data.
            self.results['rotation_angle']: Detected rotation angle (if detect_rotation=True).
        """
        # Get image from DICOM series if available
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.ctp401_slice_index)
            else:
                # Select single slice without averaging
                slice_data = self.dicom_series[self.ctp401_slice_index]
                self.image = slice_data['image']
                spacing_raw = slice_data['metadata'].get('Spacing')
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None

        spacing = self.spacing[0] if self.spacing else 1.0
        
        # Initialize analyzer - it will compute its own center and boundary
        analyzer = CTP401Analyzer(
            image=self.image,
            center=None,
            pixel_spacing=spacing,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )

        # Detect rotation if requested and t_offset not provided
        if t_offset is None and detect_rotation:
            rotation_angle = analyzer.detect_rotation()
            t_offset = rotation_angle
            self.results['rotation_angle'] = float(rotation_angle)
            print(f"🔄 Detected rotation: {rotation_angle:.2f}°")
        elif t_offset is not None:
            self.results['rotation_angle'] = float(t_offset)

        # Run analysis with detected or provided rotation offset
        res = analyzer.analyze(t_offset=t_offset if t_offset is not None else 0, verbose=True)
        self.results['ctp401'] = res

        # Store the analyzer:
        self._ctp401_analyzer = analyzer
    # ------------------ As yet undeveloped modules ---------------- 

    def run_ctp515(self, crop_x=0, crop_y=0, angle_offset: float = None):
        """
        Run low-contrast detectability analysis (CTP515 module).

        Detects low-contrast inserts of varying diameters and computes CNR
        and contrast values to assess detectability. Uses geometric center
        of potentially cropped image. Will use rotation angle from CTP401 if available.

        Args:
            crop_x (int): Number of pixels to crop from left and right edges.
            crop_y (int): Number of pixels to crop from top and bottom edges.
            angle_offset (float, optional): Manual angle offset in degrees.
                                          If None, uses rotation_angle from results.

        Populates:
            self.results['ctp515']: Low-contrast ROI statistics, CNR, and contrast values.
        """
        # Get image from DICOM series if available
        if self.dicom_series is not None:
            if self.use_slice_averaging:
                self.image, self.spacing = self._average_slices(self.ctp515_slice_index)
            else:
                # Select single slice without averaging
                slice_data = self.dicom_series[self.ctp515_slice_index]
                self.image = slice_data['image']
                spacing_raw = slice_data['metadata'].get('Spacing')
                self.spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None
        
        # Crop the image if requested
        if crop_x > 0 or crop_y > 0:
            h, w = self.image.shape
            cropped_image = self.image[crop_y:h-crop_y, crop_x:w-crop_x]
        else:
            cropped_image = self.image

        # Use detected rotation angle if available and angle_offset not provided
        if angle_offset is None:
            angle_offset = self.results.get('rotation_angle', 0.0)
            if 'rotation_angle' in self.results:
                print(f"📐 Using detected rotation angle: {angle_offset:.2f}° for CTP515")

        spacing = self.spacing[0] if self.spacing else 1.0
        
        # Initialize analyzer - it will compute its own center and boundary
        analyzer = CTP515Analyzer(
            cropped_image,
            center=None,
            pixel_spacing=spacing,
            angle_offset=angle_offset,
            center_threshold=self.center_threshold,
            center_threshold_fallback=self.center_threshold_fallback
        )
        
        # Store the results of the analysis:
        res = analyzer.analyze()
        self.results['ctp515'] = res

        # Store the analyzer:
        self._ctp515_analyzer = analyzer


    # ------------------ Helper functions ------------------
    def _average_slices(self, slice_index: int) -> Tuple[np.ndarray, Optional[Tuple[float, float]]]:
        """
        Average a slice with its two neighboring slices.
        
        Averages the specified slice with the slices immediately before and after it
        (e.g., if slice_index=50, averages slices 49, 50, 51). Handles edge cases
        by only averaging available slices.
        
        Args:
            slice_index (int): Index of the center slice to average.
        
        Returns:
            Tuple[np.ndarray, Optional[Tuple[float, float]]]: 
                - Averaged image array
                - Pixel spacing from the center slice metadata
        
        Raises:
            ValueError: If dicom_series is not available or slice_index is out of range.
        """
        if self.dicom_series is None:
            raise ValueError("Cannot average slices: no DICOM series loaded")
        
        if slice_index < 0 or slice_index >= len(self.dicom_series):
            raise ValueError(f"Slice index {slice_index} out of range (0-{len(self.dicom_series)-1})")
        
        # Determine which slices to average
        start_idx = max(0, slice_index - 1)
        end_idx = min(len(self.dicom_series) - 1, slice_index + 1)
        
        # Collect images to average
        images_to_average = []
        for idx in range(start_idx, end_idx + 1):
            images_to_average.append(self.dicom_series[idx]['image'])
        
        # Average the images
        averaged_image = np.mean(images_to_average, axis=0)
        
        # Get spacing from the center slice
        center_metadata = self.dicom_series[slice_index]['metadata']
        spacing_raw = center_metadata.get('Spacing')
        spacing = (float(spacing_raw[0]), float(spacing_raw[1])) if spacing_raw else None
        
        return averaged_image, spacing
    

    def save_results_json(self, path):
        """
        Save all collected analysis results to a JSON file.

        Args:
            path (str | Path): Where to save the JSON output.

        Raises:
            ValueError: If no analysis results exist yet.
            OSError: If writing the file fails.
        """
        if not self.results:
            raise ValueError(
                "No results available. Run at least one analysis module before saving."
            )

        out_path = Path(path)

        # Create parent directory if needed
        if out_path.parent != Path('.'):
            out_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, indent=2, cls=NumpyEncoder)
        except OSError as e:
            raise OSError(f"Failed to write JSON to {out_path}: {e}")

        return out_path

    def run_full_analysis(self, modules=None):
        """
        Run complete analysis workflow with proper module ordering.
        
        This method orchestrates the analysis of multiple modules, ensuring
        proper dependencies are maintained (uniformity detects center, CTP401
        detects rotation, then other modules use those results).
        
        Args:
            modules (list, optional): List of module names to run.
                Valid options: 'uniformity', 'detailed_uniformity', 'high_contrast', 'ctp401', 'ctp515'
                If None, runs all modules in proper order.
                
        Returns:
            dict: Dictionary containing all analysis results.
            
        Example:
            >>> analyzer = Catphan404Analyzer(dicom_series=series)
            >>> results = analyzer.run_full_analysis()
            >>> results = analyzer.run_full_analysis(modules=['uniformity', 'ctp401'])
        """
        # Default to all modules in proper order
        if modules is None:
            modules = ['uniformity', 'detailed_uniformity', 'ctp401', 'high_contrast', 'ctp515']
        
        # Always run in this order to maintain dependencies:
        # 1. uniformity (detects center)
        # 2. ctp401 (detects rotation)
        # 3. high_contrast (uses rotation)
        # 4. ctp515 (uses rotation)
        
        ordered_modules = []
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
        
        # Run each module
        for module_name in ordered_modules:
            run_method = f'run_{module_name}'
            if hasattr(self, run_method):
                getattr(self, run_method)()
                print(f"✅ Completed: {module_name}")
            else:
                print(f"⚠️  Method '{run_method}' not found. Skipping.")
        
        return self.results

    def plot_uniformity(self):
        """Create the uniformity plot for the most recent analysis."""
        if self._uniformity_analyzer is None:
            raise ValueError("Uniformity analyzer not initialized. Run run_uniformity first.")
        return UniformityPlotter(self._uniformity_analyzer).plot()

    def plot_detailed_uniformity(self):
        """Create the detailed uniformity plot for the most recent analysis."""
        if self._detailed_uniformity_analyzer is None:
            raise ValueError("Detailed uniformity analyzer not initialized. Run run_detailed_uniformity first.")
        return DetailedUniformityPlotter(self._detailed_uniformity_analyzer).plot()

    def plot_high_contrast(self):
        """Create the high contrast plot for the most recent analysis."""
        if self._high_contrast_analyzer is None:
            raise ValueError("High contrast analyzer not initialized. Run run_high_contrast first.")
        return HighContrastPlotter(self._high_contrast_analyzer).plot()

    def plot_ctp401(self):
        """Create the CTP401 plot for the most recent analysis."""
        if self._ctp401_analyzer is None:
            raise ValueError("CTP401 analyzer not initialized. Run run_ctp401 first.")
        return CTP401Plotter(self._ctp401_analyzer).plot()

    def plot_ctp515(self):
        """Create the CTP515 plot for the most recent analysis."""
        if self._ctp515_analyzer is None:
            raise ValueError("CTP515 analyzer not initialized. Run run_ctp515 first.")
        return CTP515Plotter(self._ctp515_analyzer).plot()

    def generate_plots(self, modules=None, save_plot_path: Optional[Path] = None, show_plot: bool = False):
        """
        Generate plots for one or more modules.

        Args:
            modules (list[str] | None): Modules to plot. Defaults to all modules.
            save_plot_path (Path | None): Directory or file prefix for saving plots.
            show_plot (bool): Whether to display plots interactively.

        Returns:
            dict: Mapping of module name to matplotlib Figure.
        """
        plotters = {
            'uniformity': self.plot_uniformity,
            'detailed_uniformity': self.plot_detailed_uniformity,
            'high_contrast': self.plot_high_contrast,
            'ctp401': self.plot_ctp401,
            'ctp515': self.plot_ctp515
        }

        if modules is None:
            modules = ['uniformity', 'detailed_uniformity', 'high_contrast', 'ctp401', 'ctp515']

        figures = {}
        for module in modules:
            plot_func = plotters.get(module)
            if plot_func is None:
                raise ValueError(f"No plotter available for module '{module}'")

            fig = plot_func()
            figures[module] = fig

            if save_plot_path is not None:
                if save_plot_path.is_dir():
                    target_path = save_plot_path / f"{module}.png"
                else:
                    suffix = save_plot_path.suffix if save_plot_path.suffix else ".png"
                    target_path = save_plot_path.with_name(save_plot_path.stem + f"_{module}" + suffix)
                fig.savefig(target_path)

            if show_plot:
                plt.show()
            else:
                plt.close(fig)

        return figures

    @classmethod
    def run_full_analysis_from_test_data(cls):
        """
        Convenience method for running analysis on test data in test_scans/ directory.
        
        This is primarily used for quick testing and debugging.
        
        Returns:
            Catphan404Analyzer: Analyzer instance with results, or None if failed.
        """
        from .io import load_dicom_series
        import os
        
        # Check if test_scans directory exists
        test_dir = os.path.join(os.path.dirname(__file__), 'test_scans')
        if not os.path.exists(test_dir):
            print(f"Test directory not found: {test_dir}")
            print("Run from the Catphan404 package directory to use test data.")
            return None
        
        print(f"Loading test data from: {test_dir}")
        series = load_dicom_series(test_dir)
        
        if not series:
            print("No DICOM files found in test_scans/")
            return None
        
        print(f"✅ Loaded {len(series)} DICOM slices")
        
        # Create analyzer and run full analysis
        analyzer = cls(dicom_series=series, use_slice_averaging=True)
        print("\n=== Running full analysis ===")
        analyzer.run_full_analysis()
        
        # Print summary
        print(f"\n✓ Center detected: {analyzer.results.get('center')}")
        print(f"✓ Rotation detected: {analyzer.results.get('rotation_angle', 'N/A')}°")
        print(f"✓ Uniformity: {analyzer.results.get('uniformity', {}).get('uniformity', 'N/A')}%")
        print("\nTest complete!")
        
        return analyzer


if __name__ == "__main__":
    # Quick test with sample data
    Catphan404Analyzer.run_full_analysis_from_test_data()