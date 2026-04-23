#!/usr/bin/env bash
# package.sh — build the Chrome Web Store upload zip.
#
# Output: dist/smartstudy-agent-v<version>.zip
#
# Excludes files the store doesn't need: screenshots, markdown docs,
# the package script itself, and the dist folder.

set -e
cd "$(dirname "$0")"

VERSION=$(node -e "console.log(JSON.parse(require('fs').readFileSync('manifest.json')).version)" 2>/dev/null \
          || grep -oP '"version"\s*:\s*"\K[^"]+' manifest.json)
OUT_DIR="dist"
OUT_FILE="$OUT_DIR/smartstudy-agent-v${VERSION}.zip"

mkdir -p "$OUT_DIR"
rm -f "$OUT_FILE"

echo ">> Packaging v${VERSION}..."

if command -v zip >/dev/null 2>&1; then
  zip -qr "$OUT_FILE" . \
    -x "dist/*" \
    -x "screenshots/*" \
    -x "*.md" \
    -x "package.sh" \
    -x ".DS_Store"
else
  # Fallback to python's zipfile when the `zip` CLI is unavailable (e.g. minimal WSL).
  python3 - "$OUT_FILE" <<'PY'
import os, sys, zipfile
out = sys.argv[1]
excludes_prefix = ("dist/", "screenshots/")
excludes_exact = ("package.sh", ".DS_Store")
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for root, _, files in os.walk("."):
        rel_root = os.path.relpath(root, ".")
        if rel_root.startswith(excludes_prefix):
            continue
        for name in files:
            rel = os.path.normpath(os.path.join(rel_root, name))
            if rel.startswith(excludes_prefix) or rel in excludes_exact:
                continue
            if rel.endswith(".md"):
                continue
            z.write(os.path.join(root, name), rel)
PY
fi

SIZE=$(du -h "$OUT_FILE" | cut -f1)
echo ">> Saved: $OUT_FILE  (${SIZE})"
echo ">> Next:   upload to https://chrome.google.com/webstore/devconsole"
