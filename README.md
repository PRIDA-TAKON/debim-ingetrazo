# debim-ingetrazo

An open-source extension for the **IngeTrazo 3D architectural modeler** that loads and synchronizes `.debim` (Declarative Building-as-Code) models.

---

## Overview

`debim-ingetrazo` enables OpenBIM manifest loading and live synchronization within IngeTrazo. It parses declarative `.debim` specification manifests and constructs native 3D geometry entities in IngeTrazo.

## Metadata

* **ID:** `debim-ingetrazo`
* **Name:** `debim — Building-as-Code Loader`
* **Version:** `0.1.0`
* **Author:** PRIDA-TAKON
* **License:** MIT
* **Min IngeTrazo Version:** `0.5.8`

---

## Installation

To install `debim-ingetrazo`, copy or extract the `debim_ingetrazo` directory into your operating system's IngeTrazo plugin folder:

### Windows
```text
%APPDATA%\ingetrazo\plugins\
```
(e.g., `C:\Users\<Username>\AppData\Roaming\ingetrazo\plugins\debim_ingetrazo`)

### Linux
```text
~/.local/share/ingetrazo/plugins/
```
(e.g., `/home/<username>/.local/share/ingetrazo/plugins/debim_ingetrazo`)

### macOS
Extract `debim_ingetrazo` into the IngeTrazo application plugins directory under your user Application Support or user plugins path.

---

## Developer Guidelines

### Prerequisites

* Python 3.10+
* `pytest` for running test suites

### Packaging the Extension

To build the distribution archive and calculate its SHA-256 hash:

```bash
python tools/package_extension.py
```

This will produce `dist/debim-ingetrazo.zip` and output the package checksum:

```text
Extension packaged successfully: /path/to/dist/debim-ingetrazo.zip
SHA-256: <digest>
```

### Running Tests

Run unit tests locally using `pytest`:

```bash
pytest
```

---

## License

Distributed under the [MIT License](LICENSE).
