"""Command-line entry points for CT-CatPhan.

This module exposes the package's CLI argument parsing and command execution
workflow. Its responsibilities are intentionally orchestration-focused:

- interpret command-line options,
- load either a DICOM series or a single image,
- create a :class:`catphan500.analysis.Catphan500Analyzer`,
- dispatch the requested analysis modules, and
- optionally save JSON results and diagnostic plots.

The underlying numerical work is delegated to the analyzer and its backend.
"""

import argparse
import json
from pathlib import Path
from .io import load_image, select_dicom_folder, load_dicom_series
from .analysis import Catphan500Analyzer


# Enumerate every user-selectable module name that the CLI accepts. This list
# includes the ``full_analysis`` convenience alias in addition to real modules.
AVAILABLE_MODULES = [
    'uniformity',
    'detailed_uniformity',
    'high_contrast',
    'ctp401',
    'ctp515',
    'full_analysis'  # Shortcut to run all modules
]

# Store the dependency-aware execution order for the real analysis modules. The
# order matters because CTP401 can produce a rotation angle reused later.
ANALYSIS_MODULES = [
    'uniformity',      # First: detect phantom center
    'detailed_uniformity',  # Detailed concentric profiles (same slice)
    'ctp401',          # Second: detect rotation angle using air ROIs
    'high_contrast',   # Third: uses detected rotation for line pair analysis
    'ctp515'           # Fourth: uses detected rotation for low-contrast targets
]



def parse_args():
    """
    Parse command-line arguments for the ``catphan500`` command.
    
    Returns:
        argparse.Namespace: Parsed arguments describing the requested input,
            selected modules, output behavior, and plot behavior.
    """
    # Build the CLI parser with descriptions that reflect the current package
    # behavior and supported workflow modes.
    parser = argparse.ArgumentParser(description="catphan500 analysis CLI")
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
    """Execute the CLI workflow using already-parsed arguments.

    Args:
        args (argparse.Namespace): Parsed command-line arguments produced by
            :func:`parse_args`.

    Returns:
        None: This function communicates status via terminal output.
    """
    
    # Start from the user-provided input path. This may remain ``None`` if the
    # caller wants the GUI folder chooser to be opened.
    input_path = args.input_path  # Raw input path provided by the CLI caller.
    
    # Fall back to a folder-selection dialog when the user omitted the input
    # path entirely.
    if input_path is None:
        print("Opening folder selection dialog...")
        input_path = select_dicom_folder()  # Folder chosen interactively by the user.
        if input_path is None:
            print("❌ No folder selected. Exiting.")
            return
        args.folder = True
        print(f"📁 Selected: {input_path}")
    
    # Default to DICOM-series mode unless the caller explicitly requests the
    # single-image workflow.
    use_folder_mode = not args.single_image  # True when the CLI should load a DICOM series.
    if args.folder:
        use_folder_mode = True
    
    # Load image data according to the selected operating mode.
    if use_folder_mode:
        # In folder mode, recursively load a DICOM series and build an analyzer
        # that can orchestrate module-specific slice selection.
        print(f"Loading DICOM series from: {input_path}")
        try:
            dicom_series = load_dicom_series(input_path)  # Full DICOM series loaded from the chosen folder.
            print(f"✅ Loaded {len(dicom_series)} DICOM slices")
            
            # Report slice-averaging mode so the user can confirm the intended
            # noise-reduction behavior.
            if args.average_slices:
                print("🔄 3-slice averaging enabled")
            
            analyzer = Catphan500Analyzer(
                dicom_series=dicom_series,  # Full DICOM series used for module orchestration.
                use_slice_averaging=args.average_slices  # Slice-averaging preference from the CLI.
            )
        except Exception as e:
            print(f"❌ Failed to load DICOM series: {e}")
            return
    else:
        # In single-image mode, load one image directly and build an analyzer
        # configured for immediate image-level analysis.
        print(f"Loading single image from: {input_path}")
        try:
            img, meta = load_image(input_path)  # Image array and metadata loaded from the requested file.
            analyzer = Catphan500Analyzer(image=img, spacing=meta.get('Spacing'))  # Analyzer configured for single-image mode.
        except Exception as e:
            print(f"❌ Failed to load image: {e}")
            return

    # Begin with the modules requested by the caller. This list may be replaced
    # by the full default sequence when ``full_analysis`` is present.
    modules_to_run = args.modules  # Module names requested on the command line.
    
    # Replace the shortcut alias with the dependency-aware full module list.
    if 'full_analysis' in modules_to_run:
        modules_to_run = ANALYSIS_MODULES
        print("Running full analysis (all modules)...")

    # Delegate the actual multi-module workflow to the analyzer object.
    try:
        analyzer.run_full_analysis(modules=modules_to_run)
    except ImportError as e:
        print(f"❌ {e}")
        return

    # Resolve the output JSON path. If the caller did not provide one, build a
    # filename from the requested module names.
    out_path = Path(args.out) if args.out else Path("_".join(modules_to_run) + ".json")  # JSON report path.

    # Persist results unless the caller explicitly disabled saving.
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

    # Generate plots when requested by the caller.
    if args.plot:
        # Determine whether this invocation used the ``full_analysis`` shortcut,
        # which changes the default plot-saving behavior.
        is_full_analysis = 'full_analysis' in args.modules  # True when the caller used the shortcut alias.
        save_plot_path = Path(args.save_plot) if args.save_plot else None  # Optional directory path or filename prefix for plot output.
        
        # When full analysis is requested, default to saving plots in the current
        # directory even if no explicit plot output path was supplied.
        if is_full_analysis and save_plot_path is None:
            save_plot_path = Path('.')  # Save to current directory
        try:
            analyzer.generate_plots(
                modules=modules_to_run,
                save_plot_path=save_plot_path,
                show_plot=args.show_plot
            )
        except ImportError as e:
            print(f"❌ Plotting failed: {e}")
        except Exception as e:
            print(f"❌ Plotting failed: {e}")

    # Print a concise terminal summary at the end of the run.
    print("\nModules run:", ", ".join(modules_to_run))
    if analyzer.results:
        print("Result keys in JSON:", ", ".join(analyzer.results.keys()))
    else:
        print("No results present in analyzer.results (may be empty).")


def main():
    """CLI entry point used by console-script and module execution.

    Returns:
        None: This function exists to parse arguments and dispatch execution.
    """
    args = parse_args()
    run_cli(args)


if __name__ == "__main__":
    main()
