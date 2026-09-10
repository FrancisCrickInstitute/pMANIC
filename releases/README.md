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
4. Build both installers on GitHub. You do not need a Windows PC or a Mac for this.
   1. Open the **Actions** tab.
   2. Select **Build Windows installer**, click **Run workflow**, and type the tag (`v5.0.0-alpha`).
   3. Select **Build macOS installer**, click **Run workflow**, and type the same tag.
   4. Wait until both jobs show a green tick. The page should then list `MANIC-Setup-Windows.zip` and `MANIC-Setup-Mac.dmg.zip`.
5. Stop. Do not run `scripts/publish_latest_version.sh`. Testers use the alpha page. Everyone else stays on 4.1.0.

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
