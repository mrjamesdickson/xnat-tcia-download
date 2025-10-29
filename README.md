# XNAT TCIA Download Command

This repository contains a containerised XNAT command that fetches imaging series from The Cancer Imaging Archive (TCIA) and uploads them directly into an XNAT project. It handles project creation, session labelling, and bundles both the original and post-processed manifests with each run.

## Quick Start

### Clone and install dependencies (optional)

```bash
git clone https://github.com/mrjamesdickson/xnat-tcia-download.git
cd xnat-tcia-download
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

### Run the helper script

```bash
./run_manifest.sh
```

The script:

1. Lists available `.tcia` manifests (local and inside the Docker image).
2. Prompts for:
   - XNAT host (e.g. `https://my-xnat.example`)
   - Project ID
   - Username and password
   - Manifest file path
   - Output directory (defaults to `/tmp/xnat-tcia-output`)
3. Runs the official Docker image (`xnatworks/xnat-tcia-download:1.3.1` by default) with the required mounts and arguments.

### Run directly via Python

```bash
. .venv/bin/activate  # optional if you want to use the local virtualenv
python download.py <manifest.tcia> <output_dir> <project_id> <xnat_host> <xnat_user> <xnat_pass>
```

Parameters:

| Argument        | Description                                                                                     |
|-----------------|-------------------------------------------------------------------------------------------------|
| `<manifest.tcia>` | Path to a TCIA manifest (or supported CSV) listing SeriesInstanceUIDs                         |
| `<output_dir>`    | Local workspace directory; per-series downloads are staged here                               |
| `<project_id>`    | Target XNAT project ID; the script creates it automatically if it doesn’t exist               |
| `<xnat_host>`     | XNAT base URL (e.g. `https://my-xnat.example`)                                                 |
| `<xnat_user>`     | XNAT username with project upload rights                                                       |
| `<xnat_pass>`     | XNAT password                                                                                  |

Example:

```bash
python download.py resources/TCIA/CMB-CRC_CT_small.tcia /tmp/tcia-output CMB-CRC_DEVTEST https://lustre-test.dev.xnatworks.io admin "MyPassword123!"
```

## Features

- **Dockerised workflow:** official image `xnatworks/xnat-tcia-download:1.3.1`.
- **Patient/session labelling:** preserves PatientName while generating unique session labels (`PatientID`, `PatientID_01`, …) per study.
- **Project auto-creation:** creates the XNAT project if it doesn’t already exist.
- **Manifest uploads:** attaches both the original manifest and a “modified” manifest (Series UID → session label) to the project resources.
- **Duplicate-safe commits:** avoids re-archiving sessions that already exist; cleans up the prearchive when duplicates are detected.

## Sample Manifests

The `resources/TCIA/` directory contains a mix of TCIA manifests you can use for testing, e.g.:

- `CMB-AML_v04_20240828_test.tcia`
- `CMB-CRC_CT_small.tcia`
- `CMB-CRC_CT_triple.tcia`

Feel free to add your own manifests or point the script at files stored elsewhere.

## Building the Docker Image

```bash
docker build -t xnatworks/xnat-tcia-download:1.3.1 .
```

To publish:

```bash
docker push xnatworks/xnat-tcia-download:1.3.1
docker push xnatworks/xnat-tcia-download:latest
```

## Versioning

- Current release: **1.3.1**
- Git tags reflect published versions (e.g. `v1.3.1`).
