#!/bin/bash
# Point the in-app update checker at a published release. See releases/README.md.

if [ -z "$1" ]; then
    echo "Usage: $0 <released_version>"
    echo "Example: $0 5.0.0"
    exit 1
fi

VERSION=$1

if ! [[ $VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format X.Y.Z (e.g., 5.0.0)"
    exit 1
fi

if command -v gh >/dev/null; then
    IS_DRAFT=$(gh release view "v$VERSION" --json isDraft -q .isDraft 2>/dev/null)
    if [ "$IS_DRAFT" != "false" ]; then
        echo "Error: no published GitHub Release tagged v$VERSION. Publish it first."
        exit 1
    fi
fi

cat > releases/latest.json <<EOF
{
  "version": "$VERSION",
  "url": "https://github.com/FrancisCrickInstitute/pMANIC/releases/tag/v$VERSION"
}
EOF

echo "✓ releases/latest.json now advertises v$VERSION. Commit it to main."
