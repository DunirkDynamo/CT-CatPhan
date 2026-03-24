# File: catphan404/cli.py
import argparse
import json
from pathlib import Path
from .io import load_image, select_dicom_folder, load_dicom_series
from .analysis import Catphan404Analyzer


AVAILABLE_MODULES = [
    'uniformity',
    'detailed_uniformity',
    'high_contrast',
    'ctp401',
    'ctp515',
    'full_analysis'  # Shortcut to run all modules
]

# List of actual analysis modules (excludes shortcuts)
# Order matters: uniformity detects center, ctp401 detects rotation, then others use it
ANALYSIS_MODULES = [
    'uniformity',      # First: detect phantom center
    'detailed_uniformity',  # Detailed concentric profiles (same slice)
    'ctp401',          # Second: detect rotation angle using air ROIs
    'high_contrast',   # Third: uses detected rotation for line pair analysis
    'ctp515'           # Fourth: uses detected rotation for low-contrast targets
]



def parse_args():
    """
    Parse command-line arguments for the Catphan 404 CLI.
    
    Returns:
        argparse.Namespace: Parsed arguments containing image/folder path, modules,
                           output path, plot flags, and save directory.
    """
    parser = argparse.ArgumentParser(description="Catphan 404 analysis CLI")
    parser.add_argument(
        'input_path',
        nargs='?',
        default=None,
        help="Path to DICOM folder (recommended). If omitted, opens folder selection dialog. Use --single-image for legacy single-slice mode."
    )
    parser.add_argument(
        '--folder', '-f',
        action='store_true',
        help="Explicitly treat input_path as a DICOM folder (default when input_path is provided)"
    )
    parser.add_argument(
        '--single-image',
        action='store_true',
        help="Legacy mode: treat input_path as a single image file (DICOM, PNG, TIFF, JPG). No slice averaging."
    )
    parser.add_argument(
        '--average-slices',
        action='store_true',
        help="Enable 3-slice averaging (averages target slice with neighbors). Only works in folder mode."
    )
    parser.add_argument(
        '--modules', '-m',
        nargs='+',
        choices=AVAILABLE_MODULES,
        required=True,
        help="Which analysis module(s) to run. Use 'full_analysis' to run all modules."
    )
    parser.add_argument(
        '--out', '-o',
        type=str,
        default=None,
        help="JSON output path (default: derived from module names)"
    )
    parser.add_argument(
        '--no-save',
        action='store_true',
        help="Do not save results to JSON (useful for dry-run/debug)"
    )
    parser.add_argument(
        '--plot',
        action='store_true',
        help="Generate diagnostic plots using separate plotter classes"
    )
    parser.add_argument(
        '--save-plot',
        type=str,
        default=None,
        help="Directory or file prefix to save plots (PNG)"
    )
    parser.add_argument(
        '--show-plot',
        action='store_true',
        help="Display plots interactively (default: only save for full_analysis)"
    )
    return parser.parse_args()


def run_cli(args):
    """Run analysis and optionally generate plots using separate plotter classes."""
    
    # Determine input path
    input_path = args.input_path
    
    # If no path provided, open folder selection dialog
    if input_path is None:
        print("Opening folder selection dialog...")
        input_path = select_dicom_folder()
        if input_path is None:
            print("❌ No folder selected. Exiting.")
            return
        args.folder = True
        print(f"📁 Selected: {input_path}")
    
    # Determine mode: default to folder unless --single-image is specified
    use_folder_mode = not args.single_image
    if args.folder:
        use_folder_mode = True
    
    # Load data based on mode
    if use_folder_mode:
        # DICOM series mode
        print(f"Loading DICOM series from: {input_path}")
        try:
            dicom_series = load_dicom_series(input_path)
            print(f"✅ Loaded {len(dicom_series)} DICOM slices")
            
            # Check if slice averaging is requested
            if args.average_slices:
                print("🔄 3-slice averaging enabled")
            
            analyzer = Catphan404Analyzer(
                dicom_series=dicom_series,
                use_slice_averaging=args.average_slices
            )
        except Exception as e:
            print(f"❌ Failed to load DICOM series: {e}")
            return
    else:
        # Single image mode (backwards compatible)
        print(f"Loading single image from: {input_path}")
        try:
            img, meta = load_image(input_path)
            analyzer = Catphan404Analyzer(image=img, spacing=meta.get('Spacing'))
        except Exception as e:
            print(f"❌ Failed to load image: {e}")
            return

    # Determine which modules to run
    modules_to_run = args.modules
    
    # Expand 'full_analysis' shortcut to all modules
    if 'full_analysis' in modules_to_run:
        modules_to_run = ANALYSIS_MODULES
        print("Running full analysis (all modules)...")

    # Run analysis workflow (orchestrated by the analyzer class)
    analyzer.run_full_analysis(modules=modules_to_run)

    # Decide JSON output path
    out_path = Path(args.out) if args.out else Path("_".join(modules_to_run) + ".json")

    # Save results to JSON
    if not args.no_save:
        try:
            if hasattr(analyzer, "save_results_json"):
                analyzer.save_results_json(out_path)
            else:
                with open(out_path, 'w') as f:
                    json.dump(analyzer.results, f, indent=2)
            print(f"📁 Results saved to: {out_path.resolve()}")
        except Exception as e:
            print(f"❌ Failed to save results: {e}")
    else:
        print("⚠️  Results NOT saved (--no-save)")

    # Plotting using analyzer helper
    if args.plot:
        # For full_analysis, default to saving plots
        is_full_analysis = 'full_analysis' in args.modules
        save_plot_path = Path(args.save_plot) if args.save_plot else None
        
        # Auto-enable save for full_analysis if not specified
        if is_full_analysis and save_plot_path is None:
            save_plot_path = Path('.')  # Save to current directory
        try:
            analyzer.generate_plots(
                modules=modules_to_run,
                save_plot_path=save_plot_path,
                show_plot=args.show_plot
            )
        except Exception as e:
            print(f"❌ Plotting failed: {e}")

    # Summary
    print("\nModules run:", ", ".join(modules_to_run))
    if analyzer.results:
        print("Result keys in JSON:", ", ".join(analyzer.results.keys()))
    else:
        print("No results present in analyzer.results (may be empty).")


def main():
    args = parse_args()
    run_cli(args)


if __name__ == "__main__":
    main()
