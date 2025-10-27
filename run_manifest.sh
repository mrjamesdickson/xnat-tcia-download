#!/usr/bin/env bash
# Interactive helper to launch the TCIA downloader container locally.

set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH." >&2
  exit 1
fi

DOCKER_IMAGE=${DOCKER_IMAGE:-xnatworks/xnat-tcia-download:1.3.0}

list_manifests() {
  local script_dir
  script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  local roots=(
    "${script_dir}/resources/TCIA"
    "${PWD}/resources/TCIA"
  )
  local -a manifests=()
  declare -A seen
  local root
  for root in "${roots[@]}"; do
    if [[ -d "${root}" ]]; then
      while IFS= read -r path; do
        [[ -z "${path}" ]] && continue
        path=$(cd "$(dirname "${path}")" && pwd)/"$(basename "${path}")"
        if [[ -z "${seen[${path}]:-}" ]]; then
          manifests+=("${path}")
          seen[${path}]=1
        fi
      done < <(find "${root}" -maxdepth 1 -type f -name '*.tcia' 2>/dev/null | sort)
    fi
  done
  if [[ ${#manifests[@]} -gt 0 ]]; then
    echo "Local manifest files:"
    printf '  %s\n' "${manifests[@]}"
  else
    echo "No local .tcia manifests found in ./resources/TCIA."
  fi
}

list_image_manifests() {
  echo "Checking manifests baked into ${DOCKER_IMAGE}..."
  if ! docker image inspect "${DOCKER_IMAGE}" >/dev/null 2>&1; then
    echo "  (Pulling ${DOCKER_IMAGE} metadata...)" >&2
  fi
  if ! docker run --rm "${DOCKER_IMAGE}" find /workspace/resources/TCIA -maxdepth 1 -type f -name '*.tcia' -print 2>/dev/null; then
    echo "  No manifests found inside the image or unable to list." >&2
  fi
}

list_manifests
echo
list_image_manifests

echo
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
