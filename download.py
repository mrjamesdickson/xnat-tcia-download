import sys, os
import time
import tempfile
import zipfile
import io
import requests
import pandas as pd
import xnat
import pydicom



def upload_with_rest(session, host, project, zip_path):
    """Upload DICOM ZIP to XNAT using the REST import service."""
    url = host.rstrip('/') + '/data/services/import'
    params = {
        'project': project,
        'format': 'DICOM',
        'overwrite': 'append',
        'dest': '/prearchive'
    }
    with open(zip_path, 'rb') as fp:
        files = {'file': ('img.zip', fp, 'application/zip')}
        response = session.post(url, params=params, files=files)
    print(f"    XNAT response status: {response.status_code}", flush=True)
    print(f"    XNAT response body:\n{response.text}", flush=True)
    if not response.ok:
        raise RuntimeError(f'XNAT upload failed ({response.status_code})')
    return response.text.strip()


def commit_prearchive_session(session, host, session_path):
    """Commit (archive) a prearchive session given the session path returned from upload."""
    url = host.rstrip('/') + session_path + '?action=commit'
    response = session.post(url)
    print(f"    Commit response status: {response.status_code}", flush=True)
    print(f"    Commit response body:\n{response.text}", flush=True)
    if response.status_code == 500 and "Session already exists with matching files" in response.text:
        print("    Commit detected duplicate archive; removing prearchive copy and continuing.", flush=True)
        cleanup_url = host.rstrip('/') + session_path
        cleanup_response = session.delete(cleanup_url)
        print(f"    Cleanup response status: {cleanup_response.status_code}", flush=True)
        if not cleanup_response.ok:
            print(f"    Cleanup response body:\n{cleanup_response.text}", flush=True)
        return "ALREADY_ARCHIVED"
    if response.status_code in (301, 302):
        return response.headers.get('Location', response.text.strip())
    if not response.ok:
        raise RuntimeError(f'XNAT commit failed ({response.status_code})')
    return response.text.strip()


def upload_project_file(session, host, project, resource, file_path):
    """Upload a file to a project-level resource."""
    url = (
        host.rstrip('/')
        + f"/data/projects/{project}/resources/{resource}/files/{os.path.basename(file_path)}"
    )
    params = {'overwrite': 'true'}
    with open(file_path, 'rb') as fp:
        response = session.put(
            url,
            params=params,
            data=fp,
            headers={'Content-Type': 'application/octet-stream'}
        )
    print(f"    Resource upload status ({resource}): {response.status_code}", flush=True)
    if not response.ok:
        print(f"    Resource upload body:\n{response.text}", flush=True)
        raise RuntimeError(f"Resource upload failed for {resource} ({response.status_code})")


def extract_patient_info(zip_path):
    """Return (patient_id, patient_name, study_uid) from the first DICOM in the ZIP."""
    with zipfile.ZipFile(zip_path, 'r') as zf:
        dicom_members = [name for name in zf.namelist() if name.lower().endswith('.dcm')]
        if not dicom_members:
            raise ValueError(f"No DICOM files found in {zip_path}")
        with zf.open(dicom_members[0]) as fp:
            ds = pydicom.dcmread(fp, stop_before_pixels=True, force=True)
            patient_id = ds.get('PatientID') or ""
            patient_name = ds.get('PatientName') or ""
            study_uid = ds.get('StudyInstanceUID')
    return patient_id, patient_name, study_uid


def rewrite_patient_id(zip_path, new_patient_id):
    """Rewrite PatientID (session label) without altering PatientName."""
    with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
        tmp_path = tmp.name
    try:
        with zipfile.ZipFile(zip_path, 'r') as src, zipfile.ZipFile(tmp_path, 'w', compression=zipfile.ZIP_DEFLATED) as dst:
            for entry in src.infolist():
                data = src.read(entry.filename)
                if entry.filename.lower().endswith('.dcm'):
                    ds = pydicom.dcmread(io.BytesIO(data), force=True)
                    ds.PatientID = new_patient_id
                    buffer = io.BytesIO()
                    ds.save_as(buffer, write_like_original=True)
                    data = buffer.getvalue()
                dst.writestr(entry, data)
        os.replace(tmp_path, zip_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def assign_session_label(patient_id, study_uid, patient_labels, patient_counters):
    """Compute consistent session label for patient/study, incrementing as needed."""
    base_id = patient_id or "UNKNOWN"
    key = (base_id, study_uid)
    if key in patient_labels:
        return patient_labels[key]

    count = patient_counters.get(base_id, 0)
    if count == 0:
        label = base_id
    else:
        label = f"{base_id}_{count:02d}"
    patient_labels[key] = label
    patient_counters[base_id] = count + 1
    return label


def ensure_project_exists(session, host, project):
    """Ensure the XNAT project exists; create it if missing."""
    base = host.rstrip('/')
    check_url = f"{base}/data/projects/{project}?format=json"
    response = session.get(check_url)
    if response.status_code == 200:
        return
    if response.status_code != 404:
        raise RuntimeError(
            f"Failed to query project {project}: HTTP {response.status_code}"
        )

    create_url = f"{base}/data/projects/{project}"
    payload = (
        '<xnat:ProjectData xmlns:xnat="http://nrg.wustl.edu/xnat" '
        f'ID="{project}" name="{project}"></xnat:ProjectData>'
    )
    create_resp = session.put(
        create_url,
        data=payload,
        headers={'Content-Type': 'application/xml'}
    )
    if create_resp.status_code not in (200, 201, 202):
        raise RuntimeError(
            f"Unable to create project {project}: HTTP {create_resp.status_code}"
        )

def download_series(series_instance_uid, download_path, zip_filename, chunk_size=1024 * 1024):
    """Stream a series ZIP from TCIA REST v1 endpoint."""
    os.makedirs(download_path, exist_ok=True)
    target_file = os.path.join(download_path, zip_filename)
    url = "https://services.cancerimagingarchive.net/nbia-api/services/v1/getImage"
    params = {"SeriesInstanceUID": series_instance_uid}
    print(f"  Requesting TCIA ZIP from {url}", flush=True)
    start_time = time.time()
    try:
        with requests.get(url, params=params, stream=True, timeout=(10, 600)) as response:
            response.raise_for_status()
            bytes_downloaded = 0
            with open(target_file, "wb") as fp:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    fp.write(chunk)
                    bytes_downloaded += len(chunk)
                    # Log roughly every 50 MB to show progress
                    if bytes_downloaded % (50 * chunk_size) < chunk_size:
                        elapsed = time.time() - start_time
                        mb = bytes_downloaded / (1024 * 1024)
                        speed = mb / elapsed if elapsed > 0 else 0
                        print(f"    Downloaded {mb:.1f} MB ({speed:.2f} MB/s)", flush=True)
    except requests.exceptions.RequestException as err:
        print(f"  ERROR: failed to download series {series_instance_uid}: {err}", flush=True)
        if os.path.exists(target_file):
            os.remove(target_file)
        return False

    elapsed = time.time() - start_time
    size_mb = os.path.getsize(target_file) / (1024 * 1024)
    print(f"  Download complete ({size_mb:.1f} MB in {elapsed:.1f}s).", flush=True)
    return True


def sanitize_zip(zip_path):
    """Remove non-DICOM entries to satisfy XNAT import expectations."""
    with zipfile.ZipFile(zip_path, "r") as src:
        members = src.namelist()
        dicom_members = [name for name in members if name.lower().endswith(".dcm")]
        non_dicom_count = len(members) - len(dicom_members)
        if non_dicom_count == 0:
            return

        if not dicom_members:
            raise ValueError(f"No DICOM files found in {zip_path}")

        print(f"  Removing {non_dicom_count} non-DICOM file(s) from ZIP", flush=True)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            tmp_path = tmp.name

        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as dst:
            for name in dicom_members:
                dst.writestr(name, src.read(name))

    os.replace(tmp_path, zip_path)


    
def list_manifests():
    manifest_paths = []
    search_roots = [
        os.path.join(os.path.dirname(__file__), 'resources'),
        os.getcwd()
    ]
    visited = set()
    for root in search_roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            if dirpath in visited:
                continue
            visited.add(dirpath)
            for name in filenames:
                if name.lower().endswith('.tcia'):
                    manifest_paths.append(os.path.abspath(os.path.join(dirpath, name)))
    if manifest_paths:
        print("Available TCIA manifests:")
        for path in sorted(manifest_paths):
            print(f"  {path}")
    else:
        print("No .tcia manifests found.")


if __name__ == '__main__':

    if len(sys.argv) == 1:
        list_manifests()
        sys.exit(0)

    csv_file_path = sys.argv[1]
    root_folder = sys.argv[2]
    project= sys.argv[3]
    host = sys.argv[4]
    username = sys.argv[5]
    password= sys.argv[6]

    print(f"Connecting to XNAT host {host} as user {username}", flush=True)
    xnatsession = xnat.connect(host, user=username, password=password)
    print("XNAT connection established.", flush=True)

    http_session = requests.Session()
    http_session.auth = (username, password)

    manifest_header_lines = []
    manifest_patient_map = []

    if csv_file_path.endswith('.csv'):
        print(f"Loading CSV manifest: {csv_file_path}", flush=True)
        df = pd.read_csv(csv_file_path)
        print(f"Loaded {len(df)} rows from CSV manifest.", flush=True)
    elif csv_file_path.endswith('.tcia'):
        with open(csv_file_path, 'r') as f:
            content = f.read()
        content = [x for x in content.split('\n') if len(x) > 0]
        i = content.index('ListOfSeriesToDownload=')
        manifest_header_lines = content[:i+1]
        series_instance_uid_list = content[i+1:]
        mylist = []
        for uid in series_instance_uid_list:
            mylist.append(dict(study_instance_uid='na', series_instance_uid=uid))

        df = pd.DataFrame(mylist)
        print(f"Loaded {len(df)} series from TCIA manifest: {csv_file_path}", flush=True)
    else:
        raise NotImplementedError()

    ensure_project_exists(http_session, host, project)

    patient_labels = {}
    patient_counters = {}
    session_records = []  # (session_path, series_instance_uid, session_patient_id)

    for n, row in df.iterrows():
        print(f"[{n+1}/{len(df)}] Processing series_instance_uid={row.series_instance_uid}", flush=True)
        study_instance_uid = row.study_instance_uid
        series_instance_uid = row.series_instance_uid
        if study_instance_uid == 'na':
            file_path = os.path.join(root_folder, series_instance_uid, 'img.zip')
        else:
            file_path = os.path.join(root_folder, study_instance_uid, series_instance_uid, 'img.zip')

        if os.path.exists(file_path):
            print(f"  Skipping download; file already exists at {file_path}", flush=True)
            continue

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        folder = os.path.dirname(file_path)
        basename = os.path.basename(file_path)
        print(f"  Downloading to {file_path}", flush=True)
        success = download_series(series_instance_uid, folder, basename)
        if not success:
            print(f"  ERROR: download failed for series_instance_uid={series_instance_uid}", flush=True)
            continue
        zip_file_path = folder + '/' + basename
        try:
            sanitize_zip(zip_file_path)
        except ValueError as err:
            print(f"  ERROR: {err}", flush=True)
            continue
        patient_id, patient_name, study_uid = extract_patient_info(zip_file_path)
        print(f"  Detected PatientID: {patient_id}", flush=True)
        if patient_name:
            print(f"  Detected PatientName: {patient_name}", flush=True)
        if study_uid:
            print(f"  Detected StudyInstanceUID: {study_uid}", flush=True)

        final_patient_id = assign_session_label(patient_id, study_uid, patient_labels, patient_counters)
        if final_patient_id != (patient_id or ""):
            print(f"  Rewriting PatientID (session label) to {final_patient_id}", flush=True)
            rewrite_patient_id(zip_file_path, final_patient_id)
        else:
            final_patient_id = patient_id or "UNKNOWN"

        if csv_file_path.endswith('.tcia'):
            manifest_patient_map.append((series_instance_uid, final_patient_id))
        print(f"  Uploading {zip_file_path} to XNAT project {project}", flush=True)
        try:
            session_path = upload_with_rest(http_session, host, project, zip_file_path)
            print("  Upload finished.", flush=True)
            session_records.append((session_path, series_instance_uid, final_patient_id))
        except RuntimeError as err:
            print(f"  ERROR: {err}", flush=True)
        finally:
            try:
                os.remove(zip_file_path)
                print(f"  Removed zip file: {zip_file_path}", flush=True)
            except OSError as e:
                print(f"  Warning: Could not remove zip file {zip_file_path}: {e}", flush=True)

# Commit all uploaded sessions once downloads are complete
    for session_path, series_uid, patient_id in session_records:
        print(f"Committing session for series {series_uid} (PatientID {patient_id})", flush=True)
        try:
            archive_path = commit_prearchive_session(http_session, host, session_path)
            if archive_path == "ALREADY_ARCHIVED":
                print("  Session already archived previously; moving on.", flush=True)
            else:
                print(f"  Session archived to {archive_path}", flush=True)
        except RuntimeError as err:
            print(f"  ERROR committing session {session_path}: {err}", flush=True)

    xnatsession.disconnect()

    if csv_file_path.endswith('.tcia'):
        try:
            modified_lines = manifest_header_lines.copy()
            for series_uid, patient_id in manifest_patient_map:
                modified_lines.append(f"{series_uid},{patient_id}")
            with tempfile.NamedTemporaryFile(delete=False, suffix='.tcia', mode='w') as tmp:
                tmp.write('\n'.join(modified_lines) + '\n')
                modified_manifest_path = tmp.name
            original_path = os.path.abspath(csv_file_path)
            print("Uploading manifest files to project resources...", flush=True)
            upload_project_file(http_session, host, project, 'MANIFEST_ORIGINAL', original_path)
            upload_project_file(
                http_session,
                host,
                project,
                'MANIFEST_MODIFIED',
                modified_manifest_path
            )
        finally:
            if 'modified_manifest_path' in locals() and os.path.exists(modified_manifest_path):
                os.remove(modified_manifest_path)

    print("All series processed.", flush=True)
