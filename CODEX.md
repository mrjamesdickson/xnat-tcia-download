# CODEX.md

Guidance for Codex when working in `xnat-tcia-download`. Focus on practical context, tricky edges, and how to extend or troubleshoot the tooling.

## Repository Snapshot

- **Purpose**: Containerized XNAT command that pulls imaging series listed in TCIA manifests, uploads each ZIP directly into the project prearchive, and optionally supports auxiliary bulk upload and unzip workflows.
- **Primary entry point**: `download.py` (ingests a `.tcia` manifest or CSV, downloads each series via TCIA REST, uploads to XNAT).
- **XNAT wrapper**: `command.json` + `run.sh` define how XNAT injects host/user/pass, mount paths, and the manifest filename. `command2label.py` serializes the command metadata into a Docker `LABEL`.
- **Docker image**: Built from `Dockerfile` (note existing package-install typos), copies the repo into `/workspace/`, installs Python deps from `requirements.txt`, and embeds the generated command label.

## Key Files & Roles

- `download.py`: orchestrates manifest parsing, TCIA download, and immediate upload. Skips already-downloaded series (`img.zip` presence check) and deletes zips after upload. Expects TCIA base URL `https://services.cancerimagingarchive.net/services/v3`.
- `query.py`: helper to pre-filter manifest content into CSV pairs (produces `data_series.csv`, `data_study.csv`, `data.csv`). Uses a thread pool with `maxsize=3` and caches responses on disk; be aware of the local working-directory side effects.
- `tciaclient.py`: lightweight REST client (copied from TCIA SDK) wrapping common endpoints and the `get_image` downloader that streams ZIPs to disk.
- `run.sh`: container entrypoint invoked by XNAT. Receives credentials, output mount, project ID, and manifest path; calls `download.py`. Commented lines show alternate upload/unzip pipelines.
- `upload.py` / `unzip_all.py`: legacy helpers for bulk uploads or extracting downloaded zips; both assume specific directory nesting (`root/<study>/<series>/img.zip`).
- `resources/TCIA/*.tcia`: curated manifests ready for use; filenames encode study/collection variants (e.g., `BSC-DBT-Train-manifest.tcia`, `CMB-CRC_v07_20240828.tcia`).
- `TCIA.zip`: bundled manifests archive (not unpacked by default).

## Typical Workflows

1. **XNAT command execution** (production path):
   - XNAT matches a project resource labeled `TCIA`, selects a `.tcia` file, and injects it alongside credentials and target project.
   - `run.sh` invokes `download.py manifest /input/zipped <project> <host> <user> <pass>`.
   - `download.py` builds per-series folders under `/input/zipped/`, downloads `img.zip`, uploads each to `/prearchive`, and erases the zip to conserve space.

2. **Local dry run** (manual testing):
   ```bash
   python download.py resources/TCIA/<manifest.tcia> /tmp/output <XNAT_PROJECT> <HOST> <USER> <PASS>
   ```
   Ensure `/tmp/output` exists (script will create nested folders). Set `XNAT_HOST` etc. to a test server; without XNAT access, comment out `upload()` during local debugging.

3. **Manifest preprocessing**:
   ```bash
   python query.py resources/TCIA/<manifest.tcia> manifest.csv
   ```
   Produces a filtered CSV with PET/CT pairs. Deletes or rename the generated `data_*.csv` if rerunning with different manifests.

4. **Docker build/push**:
   - `./build_and_run.sh` appends a new `LABEL` stanza to `Dockerfile` (beware of duplicates on repeated runs) then builds and pushes `xnatworks/xnat-tcia-download:1.2.0`.
   - Prefer generating the label once (`python3 command2label.py command.json > tmp && mv tmp LABEL`) to avoid multiple identical labels.

## Implementation Details & Gotchas

- **Manifest parsing**: `.tcia` files contain key-value headers followed by `ListOfSeriesToDownload=`. `download.py` strips blank lines, finds the marker, and treats the remainder as `SeriesInstanceUID`s. For `.csv` input the file must at least contain `study_instance_uid` and `series_instance_uid` columns.
- **Output layout**: For series where `study_instance_uid == 'na'`, zips land in `<root>/<series_uid>/img.zip`; otherwise in `<root>/<study_uid>/<series_uid>/img.zip`. Downstream tools rely on that structure.
- **Network usage**: `tciaclient.get_image` streams 2.5 MB chunks. Downloads are serial in `download.py`; consider batching or caching if latency is high.
- **Session cleanup**: Zips are deleted after upload, but residual directories remain. If temp storage matters, prune the empty folders or mount a tmpfs.
- **Dockerfile issues**: Contains typos (`aptg-get install pytho`, `apt-get install pip &`) that break non-cached builds. Fix before rebuilding. Also note TensorFlow base image already includes Python; redundant installs may be removable.
- **Threaded queries**: `query.py` uses `maxsize` both for the pool and to initialize `TCIAClient`. Increasing concurrency may require adjusting `TCIAClient` pool size and ensuring TCIA rate limits are respected.
- **Credentials**: XNAT credentials are passed via command args; avoid logging passwords. Wrap `xnat.connect` in try/except to surface clearer errors during automation improvements.

## Extending or Debugging

- **Add retries / error handling**: `download.py` currently skips retries if `get_image` fails; integrate TCIA retry headers (`noOfRetry`) from manifest or wrap in exponential backoff.
- **Parallel downloads**: Introduce a thread pool around the download loop to speed up large manifests. Ensure thread-safe logging and avoid overwhelming XNAT with simultaneous uploads.
- **Unit testing**: No automated tests. For additions, consider mocking `TCIAClient` (using `responses` or `urllib3` stub) and `xnat.connect` to validate manifest parsing and upload triggers.
- **Metadata enrichment**: Pair `query.py` output with `download.py` by allowing CSV rows generated from the query pipeline to drive downloads with richer metadata (e.g., log `study_date`, `collection`).

## Quick Checklist When Modifying

- Validate `command.json` remains in sync with `run.sh` arguments.
- Keep Docker label regeneration idempotent; wipe duplicated `LABEL` blocks before committing.
- Confirm new dependencies are added to `requirements.txt` and installed in the Docker image.
- If touching manifest logic, verify against a handful of files in `resources/TCIA/` to avoid regressions.
- After edits, run a smoke test against a lightweight manifest (one SeriesInstanceUID) to ensure end-to-end functionality.

