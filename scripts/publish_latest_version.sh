#!/bin/bash
# Point the in-app update checker at a published release.
#
# Run this AFTER the GitHub Release exists and its installers are uploaded,
# then commit releases/latest.json to main. Installed copies of MANIC read
# this file on start-up, so bumping it early announces a version nobody can
# download yet.

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

cat > releases/latest.json <<EOF
{
  "version": "$VERSION",
  "url": "https://github.com/FrancisCrickInstitute/pMANIC/releases/tag/v$VERSION"
}
EOF

echo "✓ releases/latest.json now advertises v$VERSION. Commit it to main."
