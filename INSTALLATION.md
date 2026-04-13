# Installation

This document describes how to install CT-CatPhan from the repository root.

The public Python package and CLI surface are both named `catphan500`.

## Requirements

- Python 3.9 or newer
- `pip`
- A working Python environment such as `venv`, Conda, or another virtual environment manager

## Runtime Installation

For normal package use, install the project in editable mode from the repository
root:

```powershell
python -m pip install -e .
```

This installs CT-CatPhan together with its runtime dependencies declared in
`pyproject.toml`, including:

- `numpy`
- `scipy`
- `pydicom`
- `matplotlib`
- `imageio`
- `scikit-image`
- `alexandria-project`

Important note:

- The backend distribution name is `alexandria-project`.
- The Python import name used by this package is `alexandria`.

## Docs Installation

If you also want to build the Sphinx documentation site locally, install the
docs extra:

```powershell
python -m pip install -e .[docs]
```

This installs the runtime dependencies plus the documentation toolchain,
including Sphinx and the Markdown parser used by the docs site.

## Verify the Installation

You can verify that the package installed correctly by importing the public
package:

```powershell
python -c "import catphan500; print(catphan500.__all__)"
```

You can also verify that the CLI entry point is available:

```powershell
catphan500 --help
```

The repository also installs a GUI launcher entry point for the simple
folder-picker workflow:

```powershell
catphan500-gui
```

## Build the Documentation Site

After installing the docs extra, build the HTML documentation from the
repository root with:

```powershell
python -m sphinx -b html docs docs/_build/html
```

The generated HTML site will be written to:

```text
docs/_build/html
```

## Recommended Development Workflow

For local development, the typical sequence is:

1. Create and activate a virtual environment.
2. Install the package with `python -m pip install -e .`.
3. If you are working on docs, install `python -m pip install -e .[docs]` instead.
4. Run the CLI or import the package in Python.

## Build a Windows Executable

For the dedicated executable build workflow, see `BUILD_EXECUTABLES.md` in the
repository root.

## Troubleshooting

### `alexandria` import cannot be resolved

If the environment reports that `alexandria` cannot be imported, reinstall the
package from the repository root:

```powershell
python -m pip install -e .
```

Remember that the install dependency is named `alexandria-project`, even though
the import used in source code is `alexandria`.

### CLI command not found

If `catphan500` is not available after installation, verify that:

- the correct virtual environment is active, and
- the editable install completed successfully.

As a fallback, you can invoke the CLI module directly:

```powershell
python -m catphan500.cli --help
```