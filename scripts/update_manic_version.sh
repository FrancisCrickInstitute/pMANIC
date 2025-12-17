#!/bin/bash

# Check if a version argument is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <new_version>"
    echo "Example: $0 4.0.1"
    exit 1
fi

NEW_VERSION=$1

# Validate version format X.Y.Z
if ! [[ $NEW_VERSION =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Error: Version must be in format X.Y.Z (e.g., 4.0.1)"
    exit 1
fi

# Extract Major, Minor, Patch for __version_info__ tuple construction
IFS='.' read -r MAJOR MINOR PATCH <<< "$NEW_VERSION"

echo "Updating application to version $NEW_VERSION..."

# 1. Update src/manic/__version__.py
# Updates: __version__ = "X.Y.Z"
sed -i.bak "s/^__version__ = \".*\"/__version__ = \"$NEW_VERSION\"/" src/manic/__version__.py
# Updates: __version_info__ = (X, Y, Z)
sed -i.bak "s/^__version_info__ = .*/__version_info__ = ($MAJOR, $MINOR, $PATCH)/" src/manic/__version__.py
echo "✓ Updated src/manic/__version__.py"

# 2. Update pyproject.toml
# Updates: version = "X.Y.Z"
sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml
echo "✓ Updated pyproject.toml"

# 3. Update installer/MANIC.iss (Windows Installer)
# Updates: AppVersion=X.Y.Z
sed -i.bak "s/^AppVersion=.*/AppVersion=$NEW_VERSION/" installer/MANIC.iss
echo "✓ Updated installer/MANIC.iss"

# 4. Update MANIC-mac.spec (macOS Build Spec)
# Updates: 'CFBundleVersion': 'X.Y.Z'
sed -i.bak "s/'CFBundleVersion': '.*'/'CFBundleVersion': '$NEW_VERSION'/" MANIC-mac.spec
# Updates: 'CFBundleShortVersionString': 'X.Y.Z'
sed -i.bak "s/'CFBundleShortVersionString': '.*'/'CFBundleShortVersionString': '$NEW_VERSION'/" MANIC-mac.spec
echo "✓ Updated MANIC-mac.spec"

# 5. Update scripts/build_macos.sh
# Updates: VERSION="X.Y.Z"
sed -i.bak "s/^VERSION=\".*\"/VERSION=\"$NEW_VERSION\"/" scripts/build_macos.sh
echo "✓ Updated scripts/build_macos.sh"

# Clean up backup files created by sed
find . -name "*.bak" -type f -delete

echo ""
echo "Successfully updated version to $NEW_VERSION in all files."
