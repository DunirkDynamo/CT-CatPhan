"""Minimal GUI launcher for running full CT-CatPhan analysis.

This module provides a Windows-friendly entry point that can be installed as a
GUI script or bundled as an executable. The workflow is intentionally simple:

1. Prompt the user to choose a DICOM folder.
2. Prompt the user to choose an output folder.
3. Prompt the user to choose the center-finding algorithm.
4. Load the series from the selected DICOM folder.
5. Run the standard full analysis pipeline.
6. Save results as JSON and plots into the selected output folder.
7. Report success or failure with a dialog box.
"""

from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from catphan500.analysis import Catphan500Analyzer
    from catphan500.io import load_dicom_series
else:
    from .analysis import Catphan500Analyzer
    from .io import load_dicom_series


DEFAULT_OUTPUT_NAME = "catphan500_full_analysis.json"

CENTER_ALGORITHM_OPTIONS = {
    "Edge-based (default)": "edge",
    "Mirror correlation": "mirror",
}


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


def choose_center_algorithm(root: tk.Tk) -> str:
    """Prompt the user to choose the center-finding algorithm."""
    selection = tk.StringVar(value="Edge-based (default)")
    chosen_algorithm = {"value": ""}

    dialog = tk.Toplevel(root)
    dialog.title("CT-CatPhan")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.transient(root)
    dialog.grab_set()

    frame = tk.Frame(dialog, padx=18, pady=16)
    frame.pack(fill="both", expand=True)

    tk.Label(
        frame,
        text="Select center-finding algorithm",
        justify="left",
    ).pack(anchor="w")

    ttk.Combobox(
        frame,
        textvariable=selection,
        values=list(CENTER_ALGORITHM_OPTIONS.keys()),
        state="readonly",
        width=28,
    ).pack(fill="x", pady=(8, 14))

    button_row = tk.Frame(frame)
    button_row.pack(anchor="e")

    def _accept() -> None:
        chosen_algorithm["value"] = CENTER_ALGORITHM_OPTIONS[selection.get()]
        dialog.destroy()

    def _cancel() -> None:
        chosen_algorithm["value"] = ""
        dialog.destroy()

    ttk.Button(button_row, text="Cancel", command=_cancel).pack(side="right")
    ttk.Button(button_row, text="OK", command=_accept).pack(side="right", padx=(0, 8))

    dialog.protocol("WM_DELETE_WINDOW", _cancel)
    dialog.update_idletasks()
    dialog.wait_window()
    return chosen_algorithm["value"]


def run_full_analysis_for_folder(folder_path: str, output_folder: str, center_algorithm: str) -> Path:
    """Run full analysis and save JSON plus plots in the chosen output folder."""
    series = load_dicom_series(folder_path)
    analyzer = Catphan500Analyzer(dicom_series=series, center_algorithm=center_algorithm)
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

    center_algorithm = choose_center_algorithm(root)
    if not center_algorithm:
        root.destroy()
        return

    progress_dialog = _show_progress_dialog(root)

    try:
        output_path = run_full_analysis_for_folder(folder_path, output_folder, center_algorithm)
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
        f"Center-finding algorithm: {center_algorithm}\n\n"
        f"JSON saved to:\n{output_path}\n\n"
        f"Plots saved to:\n{Path(output_folder)}",
        parent=root,
    )
    root.destroy()


if __name__ == "__main__":
    main()
