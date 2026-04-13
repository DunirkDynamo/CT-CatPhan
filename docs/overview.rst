Overview
========

CT-CatPhan provides a package and CLI surface for orchestrating CatPhan QA
analysis across multiple phantom modules.

Package structure
-----------------

The repository is organized around a small public package and a separate docs
tree:

.. code-block:: text

	CT-CatPhan/
	|-- src/
	|   `-- catphan500/
	|       |-- __init__.py      # Public package exports
	|       |-- analysis.py      # Main orchestration layer and plot helpers
	|       |-- cli.py           # Command-line entry point
	|       `-- io.py            # Image and DICOM loading utilities
	|-- docs/                    # Sphinx source for GitHub Pages
	|-- README.md                # Repository overview
	|-- QUICK_START.md           # Fast onboarding for users and developers
	|-- INSTALLATION.md          # Installation and environment setup
	`-- CLI_USAGE.md             # CLI reference and examples

At a high level, ``cli.py`` and the public package exports feed into
``Catphan500Analyzer`` in ``analysis.py``, which uses ``io.py`` for data
loading and delegates numerical analysis to the external ``alexandria``
backend.

The primary public entry points are:

- ``catphan500.Catphan500Analyzer``
- ``catphan500.load_image()``
- ``catphan500.load_dicom_series()``
- ``catphan500.select_dicom_folder()``

The intended primary workflow is DICOM-series analysis rather than single-image
analysis. In series mode the analyzer can:

- select module-specific slices automatically,
- optionally average neighboring slices,
- detect rotation from the CTP401 slice, and
- generate JSON results and plots after analysis completes.

Available analysis modules
--------------------------

- ``uniformity``
- ``detailed_uniformity``
- ``ctp401``
- ``high_contrast``
- ``ctp515``

The CLI also exposes ``full_analysis`` as a convenience alias for the full,
dependency-aware analysis order.
