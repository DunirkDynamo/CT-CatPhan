"""Sphinx configuration for the CT-CatPhan documentation site."""

from pathlib import Path
import sys


# Add the src/ directory so autodoc can import the public package modules.
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))


# Define the project metadata shown throughout the generated site.
project = "CT-CatPhan"
author = "Oz"
release = "0.1.0"


# Enable Sphinx extensions required for autodoc-based API reference pages.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.githubpages",
    "myst_parser",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]


# Configure autodoc output so generated API pages follow source order and work
# even when the external Alexandria backend is unavailable during doc builds.
autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_typehints = "description"
autodoc_mock_imports = [
    "alexandria",
    "alexandria.plotters",
    "alexandria.plotters.high_contrast_plotter",
    "alexandria.plotters.uniformity_plotter",
    "alexandria.plotters.ctp401_plotter",
    "alexandria.plotters.ctp515_plotter",
    "alexandria.plotters.detailed_uniformity_plotter",
]


# Support the Google-style docstrings used in the package source.
napoleon_google_docstring = True
napoleon_numpy_docstring = False


# Keep the docs build focused on source documents rather than generated output.
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}


# Use a built-in theme to keep the docs dependency footprint minimal.
html_theme = "alabaster"
html_title = "CT-CatPhan"
