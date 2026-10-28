#!/usr/bin/env bash
# Install a released Loop binary without requiring Go or administrator access.
set -euo pipefail

install_dir="${HOME}/.local/bin"
version=""
archive=""
checksums=""
repository="domhauton/loop-cli-adk"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir|--version|--archive|--checksums|--repository)
      [[ $# -ge 2 ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --dir) install_dir="$2" ;;
        --version) version="$2" ;;
        --archive) archive="$2" ;;
        --checksums) checksums="$2" ;;
        --repository) repository="$2" ;;
      esac
      shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

temp_dir="$(mktemp -d)"
stage_dir=""
trap 'rm -rf "$temp_dir"; if [[ -n "$stage_dir" ]]; then rm -rf "$stage_dir"; fi' EXIT

if [[ -z "$archive" ]]; then
  [[ "$repository" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo 'Invalid repository' >&2; exit 2; }
  if [[ -z "$version" ]]; then
    release_url="$(curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' --output /dev/null --write-out '%{url_effective}' "https://github.com/$repository/releases/latest")"
    version="${release_url##*/}"
  fi
  version="${version#v}"
  [[ "$version" =~ ^0\.[0-9]+\.[0-9]+(-[A-Za-z0-9.-]+)?$ ]] || { echo 'Expected a released v0 semantic version' >&2; exit 2; }
  case "$(uname -s)" in Darwin) platform=darwin ;; Linux) platform=linux ;; *) echo 'Unsupported OS' >&2; exit 2 ;; esac
  case "$(uname -m)" in x86_64|amd64) arch=amd64 ;; arm64|aarch64) arch=arm64 ;; *) echo 'Unsupported architecture' >&2; exit 2 ;; esac
  archive="$temp_dir/loop_${version}_${platform}_${arch}.tar.gz"
  checksums="$temp_dir/checksums.txt"
  base_url="https://github.com/$repository/releases/download/v$version"
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' "$base_url/$(basename "$archive")" --output "$archive"
  curl --fail --silent --show-error --location --proto '=https' --proto-redir '=https' "$base_url/checksums.txt" --output "$checksums"
fi

[[ -n "$checksums" && -f "$checksums" ]] || { echo 'A checksum file is required' >&2; exit 2; }
expected="$(awk -v name="$(basename "$archive")" '$2 == name {print $1}' "$checksums")"
[[ "$expected" =~ ^[a-fA-F0-9]{64}$ ]] || { echo 'Missing or ambiguous archive checksum' >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then
  actual="$(sha256sum "$archive" | awk '{print $1}')"
else
  actual="$(shasum -a 256 "$archive" | awk '{print $1}')"
fi
[[ "$actual" == "$expected" ]] || { echo 'Archive checksum mismatch' >&2; exit 1; }

mkdir -p "$install_dir"
stage_dir="$(mktemp -d "$install_dir/.loop-install.XXXXXX")"
tar -xzf "$archive" -C "$stage_dir" loop
[[ -f "$stage_dir/loop" && ! -L "$stage_dir/loop" ]] || { echo 'Archive must contain a regular loop executable' >&2; exit 1; }
chmod 755 "$stage_dir/loop"
mv -f "$stage_dir/loop" "$install_dir/loop"
echo "Installed Loop to $install_dir/loop"
echo "If needed, add $install_dir to PATH. Remove that executable to uninstall."
