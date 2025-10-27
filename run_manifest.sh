#!/usr/bin/env bash
# Interactive helper to launch the TCIA downloader container locally.

set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH." >&2
  exit 1
fi

read -rp "XNAT host (e.g. https://your-xnat): " XNAT_HOST
if [[ -z "${XNAT_HOST}" ]]; then
  echo "Host cannot be empty." >&2
  exit 1
fi

read -rp "XNAT project ID: " XNAT_PROJECT
if [[ -z "${XNAT_PROJECT}" ]]; then
  echo "Project ID cannot be empty." >&2
  exit 1
fi

read -rp "XNAT username: " XNAT_USER
if [[ -z "${XNAT_USER}" ]]; then
  echo "Username cannot be empty." >&2
  exit 1
fi

read -srp "XNAT password: " XNAT_PASS
echo
if [[ -z "${XNAT_PASS}" ]]; then
  echo "Password cannot be empty." >&2
  exit 1
fi

read -rp "Path to manifest (.tcia): " MANIFEST_PATH
if [[ ! -f "${MANIFEST_PATH}" ]]; then
  echo "Manifest file not found: ${MANIFEST_PATH}" >&2
  exit 1
fi

manifest_ext="${MANIFEST_PATH##*.}"
if [[ "${manifest_ext,,}" != "tcia" ]]; then
  echo "Manifest must be a .tcia file." >&2
  exit 1
fi

read -rp "Local output directory [/tmp/xnat-tcia-output]: " OUTPUT_DIR
OUTPUT_DIR=${OUTPUT_DIR:-/tmp/xnat-tcia-output}
mkdir -p "${OUTPUT_DIR}"

MANIFEST_DIR=$(cd "$(dirname "${MANIFEST_PATH}")" && pwd)
MANIFEST_FILE=$(basename "${MANIFEST_PATH}")
OUTPUT_DIR=$(cd "${OUTPUT_DIR}" && pwd)

DOCKER_IMAGE=${DOCKER_IMAGE:-xnatworks/xnat-tcia-download:1.2.0}

echo "Launching ${DOCKER_IMAGE}..."
docker run --rm \
  -v "${MANIFEST_DIR}":/input \
  -v "${OUTPUT_DIR}":/output \
  "${DOCKER_IMAGE}" \
  /workspace/run.sh \
    "${XNAT_HOST}" \
    "${XNAT_USER}" \
    "${XNAT_PASS}" \
    /output \
    "${XNAT_PROJECT}" \
    "/input/${MANIFEST_FILE}"

echo "Run complete. Output (including modified manifests) stored under ${OUTPUT_DIR}"
