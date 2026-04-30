#!/usr/bin/env bash
set -euo pipefail

# Update script for refind-nix
# Tracks: rEFInd upstream (SourceForge) + theme commit SHAs (GitHub)
# Contract: exit 0 = success/no-update, exit 1 = failed, exit 2 = network error

OUTPUT_FILE="${GITHUB_OUTPUT:-/tmp/update-outputs.env}"
: > "$OUTPUT_FILE"

output() { echo "$1=$2" >> "$OUTPUT_FILE"; }
log() { echo "==> $*"; }
warn() { echo "::warning::$*"; }
err() { echo "::error::$*"; }

PACKAGE="refind-nix"
output "package_name" "$PACKAGE"

log "Checking rEFInd upstream version on SourceForge..."
LATEST=$(curl -sf "https://sourceforge.net/projects/refind/files/" \
  | grep -oP '(?<=/files/)\d+\.\d+[\d.]*(?=/)' \
  | sort -V | tail -1) || { err "Failed to fetch SourceForge"; exit 2; }

log "Latest upstream rEFInd: ${LATEST}"
output "upstream_version" "$LATEST"

log "Checking theme commit SHAs..."
for theme_file in themes/*.nix; do
  [ "$theme_file" = "themes/default.nix" ] && continue
  theme_name=$(basename "$theme_file" .nix)
  CURRENT_REV=$(grep -oP 'rev = "\K[^"]+' "$theme_file" || true)
  OWNER=$(grep -oP 'owner = "\K[^"]+' "$theme_file" || true)
  REPO=$(grep -oP 'repo = "\K[^"]+' "$theme_file" || true)

  if [ -n "$OWNER" ] && [ -n "$REPO" ]; then
    LATEST_REV=$(curl -sf "https://api.github.com/repos/${OWNER}/${REPO}/commits/HEAD" \
      | jq -r '.sha' 2>/dev/null) || { warn "Failed to check ${theme_name}"; continue; }

    if [ "$CURRENT_REV" != "$LATEST_REV" ]; then
      log "Theme ${theme_name}: ${CURRENT_REV:0:8} → ${LATEST_REV:0:8}"
      output "theme_${theme_name}_update" "$LATEST_REV"
    else
      log "Theme ${theme_name}: up to date"
    fi
  fi
done

log "Update check complete."
