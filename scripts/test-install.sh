#!/usr/bin/env bash
# Exercise the real installer offline, including rejection of a damaged archive.
set -euo pipefail
temp_dir="$(mktemp -d)"
trap 'rm -rf "$temp_dir"' EXIT
CGO_ENABLED=0 go build -o "$temp_dir/loop" ./cmd/loop
tar -czf "$temp_dir/fixture.tar.gz" -C "$temp_dir" loop
if command -v sha256sum >/dev/null 2>&1; then
  checksum="$(sha256sum "$temp_dir/fixture.tar.gz" | awk '{print $1}')"
else
  checksum="$(shasum -a 256 "$temp_dir/fixture.tar.gz" | awk '{print $1}')"
fi
printf '%s  fixture.tar.gz\n' "$checksum" > "$temp_dir/checksums.txt"
bash scripts/install.sh --archive "$temp_dir/fixture.tar.gz" --checksums "$temp_dir/checksums.txt" --dir "$temp_dir/install with spaces"
[[ "$("$temp_dir/install with spaces/loop" version)" == dev ]]
# A failed upgrade must leave the installed executable intact.
printf 'damaged' >> "$temp_dir/fixture.tar.gz"
if bash scripts/install.sh --archive "$temp_dir/fixture.tar.gz" --checksums "$temp_dir/checksums.txt" --dir "$temp_dir/install with spaces"; then
  echo 'Installer accepted a damaged archive' >&2
  exit 1
fi
[[ "$("$temp_dir/install with spaces/loop" version)" == dev ]]
