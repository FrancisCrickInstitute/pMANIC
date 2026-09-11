# Publish a new version of MANIC

This file is for the person who puts a new MANIC on GitHub. Lab users can ignore it.

Two separate things both sound like "the latest version". They are not the same.

**The download page.** GitHub's [latest release](https://github.com/FrancisCrickInstitute/pMANIC/releases/latest) link. People who do not know the version number land here. GitHub ignores any page marked as a pre-release, so this link still points at 4.1.0 while 5.0 is in testing.

**The in-app update check.** Every installed copy of MANIC, on start-up, reads `releases/latest.json` from the `main` branch. That file has a version number and a URL. If the file's version is newer than the running app, MANIC shows "Update available" and opens that URL. The file still says 4.1.0. Leave it there until the lab should move.

## Testing page or lab-wide page

A **testing page** is for people who chose to try the new version. GitHub's name for this is pre-release. The tag ends in `-alpha` or `-beta`, for example `v5.0.0-alpha`. Tick **Set as a pre-release**. Do not change `latest.json`. Testers open that page on purpose. Everyone else stays on 4.1.0.

A **lab-wide page** is the version you want most people to install. GitHub's name for this is a full release. The tag is a plain number, for example `v5.0.0`. Do not tick **Set as a pre-release**. After both installers are on the page, update `latest.json` so installed copies offer the upgrade.

Do not turn an `-alpha` page into the lab-wide page. When the lab is ready, make a new tag without `-alpha`.

## Put a testing version on GitHub

Use these steps for `v5.0.0-alpha` and for any later `-beta`.

1. Put the version number in the code. Run `scripts/update_manic_version.sh 5.0.0` and commit that change to `main`. The script accepts only `X.Y.Z`. The `-alpha` part lives on the tag, not in this script.
2. Mark that commit. Create a git tag named `v5.0.0-alpha` and push the tag.
3. Make the download page. On GitHub, create a Release for that tag. The file list can start empty. Tick **Set as a pre-release**.
4. Build both installers. Follow the section **Build the Windows and Mac installers on GitHub** below.
5. Stop. Do not run `scripts/publish_latest_version.sh`. Testers use the alpha page. Everyone else stays on 4.1.0.

## Build the Windows and Mac installers on GitHub

This is the step the lists above call "build both installers". GitHub starts a rented Windows PC and a rented Mac. Each job builds one installer and attaches the zip to the release page you already made. You stay on the computer in front of you.

Do the Windows job first, then the Mac job. The clicks are the same. Only the name in the left list changes.

You must be signed into GitHub on an account that can push to this repository. If **Run workflow** is missing, you are not signed in or you do not have that access.

Create the release page for the tag before you start. The job uploads onto that page. If the page does not exist yet, the job fails.

1. Open the [Actions tab of this repository](https://github.com/FrancisCrickInstitute/pMANIC/actions).
2. In the left list, click **Build Windows installer**.
3. Above the list of past runs, click **Run workflow**.
4. A small form opens. Leave **Use workflow from** set to **main**. That field picks which copy of the recipe to use. It is not the version you are building.
5. In the **tag** box, type the release tag, for example `v5.0.0-alpha`. That is the version GitHub builds and the page it attaches the zip to.
6. Click the green **Run workflow** button.
7. A new row appears in the list, usually within a few seconds. Click the row. A yellow dot means it is still working. A green tick means it finished. A red cross means it failed.
8. Repeat steps 2 to 7. In the left list click **Build macOS installer**. Type the same tag.
9. When both rows show a green tick, open the release page for that tag. Under **Assets** you should see `MANIC-Setup-Windows.zip` and `MANIC-Setup-Mac.dmg.zip`.

The Windows job on `v5.0.0-alpha` took 7 minutes 33 seconds. The Mac job took 2 minutes 41 seconds. Those are measured on the first runs, not a promise.

If a job fails, open the red row and read the last error. Fix that, then run that one job again. You do not need to rerun the job that already went green. Running the same job again replaces that zip on the release page.

Direct links if you want to skip the left list:

* [Build Windows installer](https://github.com/FrancisCrickInstitute/pMANIC/actions/workflows/build-windows.yml)
* [Build macOS installer](https://github.com/FrancisCrickInstitute/pMANIC/actions/workflows/build-macos.yml)

## Tell the whole lab to upgrade

Do this only when the lab has accepted the new numbers and someone has opened both installers on a real lab machine.

1. Repeat the steps above. Use a tag with no suffix, for example `v5.0.0`.
2. Do not tick **Set as a pre-release**.
3. Wait until both installer zips are on that page.
4. Run `scripts/publish_latest_version.sh 5.0.0` and commit that change to `main`. From that moment, every installed copy can show "Update available".

That last step is separate on purpose. Changing `latest.json` tells the whole lab at once. Do it only after people can download the installers.

## Build an installer on your own computer

Use this only when you are debugging the installer itself.

* Windows. Run `scripts\build_windows.bat` on a Windows PC that has Inno Setup.
* Mac. Run `scripts/build_macos.sh` on a Mac. Install `create-dmg` with Homebrew if you want the styled disk image.

Otherwise use the Actions jobs above.
