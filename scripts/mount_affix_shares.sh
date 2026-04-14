#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${AFFIX_MOUNT_ENV_FILE:-$PROJECT_ROOT/config/affix_mount.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[ERROR] Mount environment file was not found: $ENV_FILE"
  echo "[INFO] Copy config/affix_mount.env.example to config/affix_mount.env and fill in the values."
  exit 1
fi

source "$ENV_FILE"

required_vars=(
  AFFIX_SERVER
  AFFIX_USERNAME
)

for var_name in "${required_vars[@]}"; do
  if [[ -z "${!var_name:-}" ]]; then
    echo "[ERROR] Missing required variable in $ENV_FILE: $var_name"
    exit 1
  fi
done

SMB_VERSION="${AFFIX_SMB_VERSION:-3.0}"
MOUNT_UID="${AFFIX_UID:-$(id -u)}"
MOUNT_GID="${AFFIX_GID:-$(id -g)}"
PASSWORD_FILE="${AFFIX_PASSWORD_FILE:-}"
PASSWORD_VALUE="${AFFIX_PASSWORD:-}"
DEFAULT_MOUNT_FLAGS="${AFFIX_MOUNT_FLAGS:-ro}"

build_options() {
  local extra_flags="${1:-}"
  local base_opts
  base_opts="username=${AFFIX_USERNAME},vers=${SMB_VERSION},uid=${MOUNT_UID},gid=${MOUNT_GID},iocharset=utf8"

  if [[ -n "$PASSWORD_FILE" ]]; then
    base_opts="${base_opts},credentials=${PASSWORD_FILE}"
  else
    base_opts="${base_opts},password=${PASSWORD_VALUE}"
  fi

  if [[ -n "$extra_flags" ]]; then
    echo "${base_opts},${extra_flags}"
  else
    echo "${base_opts}"
  fi
}

ensure_mount_point() {
  local target="$1"
  sudo mkdir -p "$target"
}

mount_share() {
  local share_name="$1"
  local mount_point="$2"
  local mount_flags="${3:-$DEFAULT_MOUNT_FLAGS}"
  local required="${4:-false}"

  if [[ -z "$share_name" || -z "$mount_point" ]]; then
    return 0
  fi

  local share_path="//${AFFIX_SERVER}/${share_name}"

  ensure_mount_point "$mount_point"

  if mountpoint -q "$mount_point"; then
    echo "[INFO] $mount_point is already mounted."
    return 0
  fi

  echo "[INFO] Mounting $share_path to $mount_point"
  if ! sudo mount -t cifs "$share_path" "$mount_point" -o "$(build_options "$mount_flags")"; then
    if [[ "$required" == "true" ]]; then
      echo "[ERROR] Failed to mount required share: $share_path"
      exit 1
    fi

    echo "[WARN] Failed to mount optional share: $share_path"
    echo "[WARN] Check the real SMB share name on 192.168.137.110 and update config/affix_mount.env."
  fi
}

umount_share() {
  local mount_point="$1"

  if [[ -z "$mount_point" ]]; then
    return 0
  fi

  if mountpoint -q "$mount_point"; then
    echo "[INFO] Unmounting $mount_point"
    sudo umount "$mount_point"
  else
    echo "[INFO] $mount_point is not mounted."
  fi
}

status_share() {
  local mount_point="$1"

  if [[ -z "$mount_point" ]]; then
    return 0
  fi

  if mountpoint -q "$mount_point"; then
    echo "[OK] Mounted: $mount_point"
  else
    echo "[WARN] Not mounted: $mount_point"
  fi
}

mount_all() {
  mount_share "${AFFIX_RESULTS_SHARE:-}" "${AFFIX_RESULTS_MOUNT:-}" "${AFFIX_RESULTS_FLAGS:-$DEFAULT_MOUNT_FLAGS}" "true"
  mount_share "${AFFIX_ALL_IMAGES_SHARE:-}" "${AFFIX_ALL_IMAGES_MOUNT:-}" "${AFFIX_ALL_IMAGES_FLAGS:-$DEFAULT_MOUNT_FLAGS}" "false"
  mount_share "${AFFIX_DB_SHARE:-}" "${AFFIX_DB_MOUNT:-}" "${AFFIX_DB_FLAGS:-$DEFAULT_MOUNT_FLAGS}" "false"
}

umount_all() {
  umount_share "${AFFIX_DB_MOUNT:-}"
  umount_share "${AFFIX_ALL_IMAGES_MOUNT:-}"
  umount_share "${AFFIX_RESULTS_MOUNT:-}"
}

status_all() {
  status_share "${AFFIX_RESULTS_MOUNT:-}"
  status_share "${AFFIX_ALL_IMAGES_MOUNT:-}"
  status_share "${AFFIX_DB_MOUNT:-}"
}

usage() {
  cat <<EOF
Usage:
  ./scripts/mount_affix_shares.sh mount
  ./scripts/mount_affix_shares.sh umount
  ./scripts/mount_affix_shares.sh restart
  ./scripts/mount_affix_shares.sh status

Optional:
  AFFIX_MOUNT_ENV_FILE=/path/to/affix_mount.env ./scripts/mount_affix_shares.sh mount
EOF
}

ACTION="${1:-mount}"

case "$ACTION" in
  mount)
    mount_all
    ;;
  umount)
    umount_all
    ;;
  restart)
    umount_all
    mount_all
    ;;
  status)
    status_all
    ;;
  *)
    usage
    exit 1
    ;;
esac
