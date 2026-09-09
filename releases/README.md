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
3. Build the installers and create the GitHub Release on the tag with them attached.
4. `scripts/publish_latest_version.sh X.Y.Z`, commit to `main`.

Step 4 is deliberately separate from step 1. The manifest announces a version to
every installed copy the moment it lands on `main`, so it must not move until the
installers are downloadable.
