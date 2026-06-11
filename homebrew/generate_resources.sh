#!/usr/bin/env bash
# Regenerates the resource blocks in Formula/engram.rb with current PyPI sha256s.
# Run this before cutting a release:
#   cd homebrew && bash generate_resources.sh
set -euo pipefail

ENGRAM_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FORMULA="$(dirname "$0")/Formula/engram.rb"

command -v brew >/dev/null || { echo "Homebrew required"; exit 1; }

echo "Resolving resource hashes (this downloads pip wheels)..."

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

python3 -m pip download \
    -r "$ENGRAM_ROOT/requirements.txt" \
    -d "$TMPDIR" \
    --no-deps \
    --quiet

echo ""
echo "Paste these resource blocks into Formula/engram.rb:"
echo ""

for wheel in "$TMPDIR"/*.tar.gz "$TMPDIR"/*.whl; do
    [[ -f "$wheel" ]] || continue
    name=$(basename "$wheel")
    sha=$(shasum -a 256 "$wheel" | awk '{print $1}')
    # Try to find the PyPI source URL
    pkg=$(echo "$name" | sed 's/-[0-9].*//')
    echo "  resource \"$pkg\" do"
    echo "    # sha256 of $name"
    echo "    sha256 \"$sha\""
    echo "  end"
    echo ""
done
