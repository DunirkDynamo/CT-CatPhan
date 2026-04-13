"""Minimal GUI launcher for running full CT-CatPhan analysis.

This module provides a Windows-friendly entry point that can be installed as a
GUI script or bundled as an executable. The workflow is intentionally simple:

1. Prompt the user to choose a DICOM folder.
2. Prompt the user to choose an output folder.
3. Load the series from the selected DICOM folder.
4. Run the standard full analysis pipeline.
5. Save results as JSON and plots into the selected output folder.
6. Report success or failure with a dialog box.
"""

from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from catphan500.analysis import Catphan500Analyzer
    from catphan500.io import load_dicom_series
else:
    from .analysis import Catphan500Analyzer
    from .io import load_dicom_series


DEFAULT_OUTPUT_NAME = "catphan500_full_analysis.json"


def _show_progress_dialog(root: tk.Tk) -> tk.Toplevel:
    """Create a small modal-style progress dialog while analysis runs."""
    dialog = tk.Toplevel(root)
    dialog.title("CT-CatPhan")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.protocol("WM_DELETE_WINDOW", lambda: None)

    label = tk.Label(
        dialog,
        text="Running full analysis...\nThis may take a moment.",
        padx=24,
        pady=18,
        justify="center",
    )
    label.pack()

    dialog.transient(root)
    dialog.grab_set()
    dialog.update_idletasks()
    return dialog


def choose_folder(root: tk.Tk) -> str:
    """Open a folder chooser and return the selected path or an empty string."""
    return filedialog.askdirectory(
        parent=root,
        title="Select Folder Containing CatPhan DICOM Data",
        mustexist=True,
    )


def choose_output_folder(root: tk.Tk, initial_dir: str) -> str:
    """Open a folder chooser for selecting where reports and plots will go."""
    return filedialog.askdirectory(
        parent=root,
        title="Select Output Folder for Results and Plots",
        mustexist=True,
        initialdir=initial_dir,
    )


def run_full_analysis_for_folder(folder_path: str, output_folder: str) -> Path:
    """Run full analysis and save JSON plus plots in the chosen output folder."""
    series = load_dicom_series(folder_path)
    analyzer = Catphan500Analyzer(dicom_series=series)
    analyzer.run_full_analysis()

    output_dir = Path(output_folder)
    output_path = output_dir / DEFAULT_OUTPUT_NAME
    analyzer.save_results_json(output_path)
    analyzer.generate_plots(save_plot_path=output_dir, show_plot=False)
    return output_path


def main() -> None:
    """Launch a folder picker and run full analysis for the selected folder."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    folder_path = choose_folder(root)
    if not folder_path:
        root.destroy()
        return

    output_folder = choose_output_folder(root, folder_path)
    if not output_folder:
        root.destroy()
        return

    progress_dialog = _show_progress_dialog(root)

    try:
        output_path = run_full_analysis_for_folder(folder_path, output_folder)
    except Exception as exc:
        progress_dialog.destroy()
        messagebox.showerror(
            "CT-CatPhan",
            f"Full analysis failed.\n\n{exc}",
            parent=root,
        )
        root.destroy()
        return

    progress_dialog.destroy()
    messagebox.showinfo(
        "CT-CatPhan",
        "Full analysis completed successfully.\n\n"
        f"JSON saved to:\n{output_path}\n\n"
        f"Plots saved to:\n{Path(output_folder)}",
        parent=root,
    )
    root.destroy()


if __name__ == "__main__":
    main()
