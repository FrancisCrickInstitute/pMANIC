# Release manifest

`latest.json` is what installed copies of MANIC read on start-up to decide whether
to show "Update available". It is fetched from
`raw.githubusercontent.com/FrancisCrickInstitute/pMANIC/main/releases/latest.json`,
which has no API rate limit, so the check keeps working on shared lab networks.

Only `version` and `url` are read. `version` is compared numerically against the
running build's `__version_info__`; `url` is the page the user is sent to.

## Cutting a release

1. `scripts/update_manic_version.sh X.Y.Z`, commit to `main`.
2. Tag that commit `vX.Y.Z` and push the tag.
3. Create the GitHub Release on that tag. Empty assets are fine. Tick **Set as a
   pre-release** for any tag that ends in `-alpha` or `-beta`.
4. From any machine, build both installers on GitHub Actions and attach them to
   the release:
   1. Actions → **Build Windows installer** → Run workflow → enter the tag.
   2. Actions → **Build macOS installer** → Run workflow → enter the same tag.
   Wait until both jobs finish. The release should then list
   `MANIC-Setup-Windows.zip` and `MANIC-Setup-Mac.dmg.zip`.
5. For a full release only (tag is `vX.Y.Z` with no suffix, and the pre-release
   checkbox is off), run `scripts/publish_latest_version.sh X.Y.Z` and commit
   that change to `main`. Skip this step for `v5.0.0-alpha` and any other
   pre-release.

Step 5 is deliberately separate from step 1. The manifest announces a version to
every installed copy the moment it lands on `main`, so it must not move until the
installers are downloadable.

Local builds still work. `scripts/build_windows.bat` needs a Windows machine
with Inno Setup. `scripts/build_macos.sh` needs a Mac with `create-dmg`. Prefer
the Actions jobs unless you are debugging the installer itself.
