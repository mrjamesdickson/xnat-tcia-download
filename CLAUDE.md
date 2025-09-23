# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an XNAT plugin for downloading medical imaging data from The Cancer Imaging Archive (TCIA) and uploading it to XNAT. The project consists of Python scripts packaged as a Docker container that integrates with XNAT's command execution framework.

## Key Components

- **download.py**: Main script that downloads DICOM series from TCIA and uploads them to XNAT
- **query.py**: Queries TCIA API to get study/series metadata and filters for PET/CT pairs 
- **tciaclient.py**: TCIA REST API client for downloading imaging data
- **upload.py**: Standalone script for bulk uploading zip files to XNAT
- **command.json**: XNAT command wrapper configuration defining plugin inputs/outputs
- **run.sh**: Docker entrypoint script that orchestrates the download process
- **resources/TCIA/**: Collection of TCIA manifest files (.tcia) containing series UIDs for various datasets

## TCIA Manifest Files

The `resources/TCIA/` directory contains manifest files from The Cancer Imaging Archive. Each `.tcia` file:

- Contains metadata (download URL, retry settings, manifest version)
- Lists DICOM series instance UIDs to download after `ListOfSeriesToDownload=`
- Represents curated datasets from different cancer imaging studies
- Can contain anywhere from dozens to thousands of series (e.g., BSC-DBT-Train-manifest.tcia has ~19k series)

Example manifest structure:
```
downloadServerUrl=https://nbia.cancerimagingarchive.net/nbia-download/servlet/DownloadServlet
includeAnnotation=true
noOfrRetry=4
databasketId=manifest-1680809675630.tcia
manifestVersion=3.0
ListOfSeriesToDownload=
1.3.6.1.4.1.14519.5.2.1.154348283216734456527602565583133455155
1.3.6.1.4.1.14519.5.2.1.278978536757772701496518285261991125085
...
```

## Build and Deployment

### Docker Build
```bash
# Generate Docker label from command.json and build image
python3 ./command2Label.py ./command.json >> Dockerfile
docker build -t xnatworks/xnat-tcia-download:1.2.0 .

# Push to registry
docker push xnatworks/xnat-tcia-download:1.2.0
```

### Quick Build Script
```bash
./build_and_run.sh
```

## Architecture

The system follows XNAT's containerized command pattern:

1. **Input Processing**: XNAT provides a `.tcia` manifest file containing series UIDs to download
2. **Data Download**: `download.py` reads the manifest and downloads each series as a zip file from TCIA
3. **XNAT Upload**: Downloaded zips are immediately uploaded to XNAT's prearchive via the XNAT REST API
4. **Docker Integration**: The entire process runs in a container managed by XNAT

## Key Dependencies

- **xnat**: Python XNAT client for REST API interactions
- **pandas**: Data manipulation for CSV/metadata processing  
- **pydicom**: DICOM file handling
- **urllib3**: HTTP client for TCIA API calls

## XNAT Integration

The plugin integrates with XNAT through:
- **Command wrapper**: `command.json` defines the plugin interface
- **File mounts**: Input files mounted to `/input` in container
- **Project context**: Operates at the XNAT project level
- **Resource matching**: Looks for TCIA resources with `.tcia` manifest files

## Data Flow

1. User selects XNAT project containing TCIA resource with `.tcia` file
2. XNAT launches container with project data mounted
3. `run.sh` calls `download.py` with XNAT credentials and manifest path
4. Script downloads series from TCIA and uploads to XNAT prearchive
5. Container exits, XNAT processes uploaded data