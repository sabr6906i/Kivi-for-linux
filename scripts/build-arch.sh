#!/usr/bin/env bash
# Build only from an explicit git snapshot: no keys, sessions or untracked files.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
version=0.1.0alpha2
tag=v0.1.0-alpha.2
source_ref=HEAD
output_dir="$repo_root/dist/arch"
usage() {
    cat <<'USAGE'
Usage: scripts/build-arch.sh [--version VERSION] [--tag RELEASE_TAG] [--ref GIT_REF] [--output DIRECTORY]

Creates a deterministic source archive, checksummed PKGBUILD, .SRCINFO and an
Arch .pkg.tar.zst with makepkg. Does not install the package, use sudo, publish
a release or modify Hyprland configuration. Missing dependencies cause failure.
USAGE
}
while (($#)); do
    case "$1" in
        --version|--tag|--ref|--output)
            (($# >= 2)) || { usage >&2; exit 2; }
            case "$1" in
                --version) version=$2;;
                --tag) tag=$2;;
                --ref) source_ref=$2;;
                --output) output_dir=$2;;
            esac
            shift 2;;
        -h|--help) usage; exit 0;;
        *) usage >&2; exit 2;;
    esac
done
[[ $version =~ ^[0-9][A-Za-z0-9._+]*$ ]] || { echo 'Invalid Arch version.' >&2; exit 2; }
[[ $tag =~ ^[A-Za-z0-9._+-]+$ ]] || { echo 'Invalid release tag.' >&2; exit 2; }
for tool in git makepkg sha256sum gzip; do
    command -v "$tool" >/dev/null || { echo "Missing build tool: $tool" >&2; exit 1; }
done
source_commit=$(git -C "$repo_root" rev-parse --verify --end-of-options "${source_ref}^{commit}")
source_epoch=$(git -C "$repo_root" show -s --format=%ct "$source_commit")
mkdir -p -- "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)
build_dir=$(mktemp -d "${TMPDIR:-/tmp}/bol-arch-build.XXXXXXXX")
trap 'rm -rf -- "$build_dir"' EXIT
source_name="bol-linux-$version.tar.gz"
git -C "$repo_root" archive --format=tar --prefix="Kivi-for-linux-$version/" "$source_commit" | gzip -n > "$build_dir/$source_name"
source_sha=$(sha256sum "$build_dir/$source_name")
source_sha=${source_sha%% *}
sed -e "s/@VERSION@/$version/g" -e "s/@TAG@/$tag/g" -e "s/@SHA256@/$source_sha/g" \
    "$repo_root/packaging/arch/PKGBUILD.in" > "$build_dir/PKGBUILD"
(
    cd -- "$build_dir"
    makepkg --printsrcinfo > .SRCINFO
    # makepkg resolves the already-present local archive without downloading.
    # Never install dependencies or invoke sudo from this release script.
    SOURCE_DATE_EPOCH="$source_epoch" makepkg --cleanbuild --noconfirm --force --nosign
)
cp -- "$build_dir/$source_name" "$output_dir/"
cp -- "$build_dir/PKGBUILD" "$output_dir/PKGBUILD"
cp -- "$build_dir/.SRCINFO" "$output_dir/.SRCINFO"
find "$build_dir" -maxdepth 1 -type f -name '*.pkg.tar.*' -exec cp -- {} "$output_dir/" \;
printf '%s\n' "$source_commit" > "$output_dir/SOURCE_COMMIT"
(
    cd -- "$output_dir"
    sha256sum "$source_name" ./*.pkg.tar.* > SHA256SUMS
)
printf 'Arch prerelease artifacts: %s\nSource commit: %s\n' "$output_dir" "$source_commit"
printf '%s\n' 'Package build success is not a clean-machine or cross-desktop runtime certification.'
