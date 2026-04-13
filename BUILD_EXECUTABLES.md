# Build Executables

This document explains how to build the Windows executable for the simple
CT-CatPhan GUI launcher.

The executable is intended for users who should be able to double-click an app,
select a folder containing CatPhan DICOM data, select an output folder, and run
the full analysis without using the command line.

This guide is written for two audiences:

- maintainers who rebuild the executable when the package version or workflow changes
- developers who want a repeatable way to produce their own executable from the repo

The repository now uses automatic versioning from git tags through
`setuptools-scm`. A tag such as `v1.2.3` becomes package version `1.2.3` during
builds.

## What the Executable Does

The GUI launcher:

1. opens a folder-selection dialog for the input DICOM folder,
2. opens a second folder-selection dialog for the output location,
3. runs the package full-analysis workflow,
4. writes `catphan500_full_analysis.json` to the chosen output folder, and
5. saves the module plot PNG files to that same output folder.

The launcher code lives in `src/catphan500/gui_launcher.py`.

The repository also includes two checked-in build assets:

- `packaging/pyinstaller/CT-CatPhan.spec`
- `scripts/build_executable.ps1`

It also includes a thin Windows wrapper:

- `scripts/build_executable.bat`

The spec file defines the PyInstaller build configuration. The PowerShell
script refreshes the editable install and runs the spec-driven build command.
The batch file simply forwards to the PowerShell script.

## Requirements

You need:

- Python 3.9 or newer
- a working virtual environment or Python installation
- the CT-CatPhan package installed with its runtime dependencies
- `pyinstaller`

## Recommended Build Environment

From the repository root, create or activate the Python environment you want to
use for the build.

Install the package and PyInstaller:

```powershell
python -m pip install -e .
python -m pip install pyinstaller
```

This matters because the executable will bundle whatever versions of
CT-CatPhan and its dependencies are installed in that environment.

## Fastest Developer Path

From the repository root, the simplest repeatable build flow is:

```powershell
.\scripts\build_executable.ps1 -InstallBuildTool
```

If someone is more comfortable with a classic Windows batch entry point, they
can use:

```bat
scripts\build_executable.bat -InstallBuildTool
```

After the first run, developers who already have PyInstaller installed can use:

```powershell
.\scripts\build_executable.ps1
```

or:

```bat
scripts\build_executable.bat
```

If you want to force a clean rebuild of the PyInstaller artifacts:

```powershell
.\scripts\build_executable.ps1 -Clean
```

or:

```bat
scripts\build_executable.bat -Clean
```

## `.ps1` Versus `.bat`

Use `scripts/build_executable.ps1` when you are already working in PowerShell and want
to run the build script directly:

```powershell
.\scripts\build_executable.ps1
```

Use `scripts/build_executable.bat` when you want a simpler Windows entry point that can
be run from Command Prompt or double-clicked in Explorer:

```bat
scripts\build_executable.bat
```

Important detail: the `.bat` file does not replace PowerShell. It just starts
the PowerShell script for you. So the batch wrapper is easier to launch, but it
still depends on PowerShell being available on the machine.

## When To Use the `.bat` Wrapper

The `.ps1` script is the real build implementation and should stay the source
of truth.

The `.bat` wrapper is useful when:

- someone is on Windows and expects a double-clickable or familiar batch entry point
- someone is not really a developer but needs to build locally from the repo
- a work computer makes downloading or running a prebuilt `.exe` difficult, but allows running local scripts and Python
- you want one obvious entry point for Windows users without duplicating build logic

That matches the use case you described: a user may not be allowed to download
and run a provided executable directly, but may still be able to clone or copy
the repository, install Python dependencies, and run the local build wrapper.

In that situation, `scripts/build_executable.bat` is the friendly entry point, while
`scripts/build_executable.ps1` remains the maintainable implementation underneath.

## Spec-Based Build Command

The repository-standard build command is:

```powershell
python -m PyInstaller packaging/pyinstaller/CT-CatPhan.spec
```

If you want PyInstaller itself to clear cached state during the run, use:

```powershell
python -m PyInstaller --clean packaging/pyinstaller/CT-CatPhan.spec
```

The checked-in `scripts/build_executable.ps1` script runs this spec through the active
Python environment so developers do not have to remember the exact command.

## Why the Spec File Matters

Keeping `packaging/pyinstaller/CT-CatPhan.spec` under version control gives maintainers and other
developers one shared source of truth for the executable build configuration.

That makes it easier to:

- rebuild the executable after version updates,
- review packaging changes in git,
- add future packaging options such as icons or bundled data files, and
- keep developer and release builds aligned.

## Output Location

After a successful build, the executable is written to:

```text
dist/CT-CatPhan.exe
```

PyInstaller also creates a `build/` folder.

If you use `scripts/build_executable.ps1 -Clean`, the script removes the old `build/`
and `dist/` folders before starting a new build.

## How to Run the Executable

Double-click:

```text
dist/CT-CatPhan.exe
```

Then:

1. choose the folder containing the CatPhan DICOM files,
2. choose the folder where outputs should be written, and
3. wait for the analysis to finish.

When the run completes, the app displays a confirmation dialog showing where
the JSON report and plot files were written.

## Expected Outputs

The output folder will typically contain:

- `catphan500_full_analysis.json`
- `uniformity.png`
- `detailed_uniformity.png`
- `ctp401.png`
- `high_contrast.png`
- `ctp515.png`

The exact plot set depends on the modules included by the current full-analysis
workflow.

## Rebuild After Code Changes

If you change the launcher, analyzer logic, dependencies, or packaging config,
rebuild the executable so the bundled app includes the updated code.

For most developers, using the repo script is the safest path:

```powershell
.\scripts\build_executable.ps1 -Clean
```

## Maintainer Update Checklist

When you make a new release or otherwise change application behavior, this is
the practical rebuild checklist:

1. update package code and any user-facing docs
2. create and push a release tag in the format `vX.Y.Z`
3. review `packaging/pyinstaller/CT-CatPhan.spec` if packaging behavior changed
4. refresh the environment with `python -m pip install -e .`
5. rebuild the executable locally with `.\scripts\build_executable.ps1 -Clean` if you want a preflight check
6. launch `dist/CT-CatPhan.exe` and run one real dataset through it
7. confirm the JSON report and plot files are written correctly
8. push the tag so GitHub Actions publishes Pages and creates the versioned release asset automatically

## Tag-Driven Automation

GitHub Actions is configured so that pushing a tag matching `v*.*.*` will:

1. build and publish the documentation site to GitHub Pages
2. build the Windows executable
3. create or update a GitHub Release for that tag
4. upload a versioned asset named like `CT-CatPhan-v1.2.3.exe`

Standard commits, merges, and branch pushes do not publish docs or create
release assets.

## Files Involved In the Executable Workflow

Developers who need to understand or customize the executable build should look
at these files first:

- `src/catphan500/gui_launcher.py` for the GUI workflow
- `pyproject.toml` for package metadata and entry points
- `packaging/pyinstaller/CT-CatPhan.spec` for the checked-in PyInstaller configuration
- `scripts/build_executable.bat` for the Windows batch entry point
- `scripts/build_executable.ps1` for the repeatable build command
- `BUILD_EXECUTABLES.md` for the documented process

## Troubleshooting

### `alexandria` import errors during build or runtime

Reinstall the project into the current environment:

```powershell
python -m pip install -e .
```

Remember that the package is installed from the distribution name
`alexandria-project`, but the import name used in code is `alexandria`.

### PyInstaller command not found

Install PyInstaller into the same environment you are using to build:

```powershell
python -m pip install pyinstaller
```

### The executable starts but cannot analyze data

Check that:

1. the selected input folder actually contains readable DICOM slices,
2. the environment used for bundling had all required dependencies installed,
3. the current code in `src/catphan500/gui_launcher.py` still matches the intended workflow, and
4. `packaging/pyinstaller/CT-CatPhan.spec` still reflects the intended packaging setup.

### You want to customize the executable later

Common next steps are:

1. add an `.ico` file and update `packaging/pyinstaller/CT-CatPhan.spec`,
2. add bundled data files in `packaging/pyinstaller/CT-CatPhan.spec`, and
3. build on the same Windows version family you expect end users to run.