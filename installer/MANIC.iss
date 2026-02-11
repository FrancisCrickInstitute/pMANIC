[Setup]
AppId=MANIC
AppName=MANIC
AppVersion=4.1.0
DefaultDirName={pf}\MANIC
DefaultGroupName=MANIC
UninstallDisplayIcon={app}\MANIC.exe
OutputDir=..\dist
OutputBaseFilename=MANIC-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableDirPage=no
DisableProgramGroupPage=no
ArchitecturesInstallIn64BitMode=x64

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  // Run this logic right before the actual installation (file copying) begins
  if CurStep = ssInstall then
  begin
    // Forcefully delete the docs directory and all its contents
    // Parameters: Path, IsDir, DeleteFiles, DeleteSubdirs
    DelTree(ExpandConstant('{app}\docs'), True, True, True);
  end;
end;

[InstallDelete]
Type: filesandordirs; Name: "{app}\docs"

[Files]
Source: "..\\dist\\MANIC\\*"; DestDir: "{app}"; Flags: recursesubdirs

[Icons]
Name: "{group}\MANIC"; Filename: "{app}\MANIC.exe"
Name: "{commondesktop}\MANIC"; Filename: "{app}\MANIC.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\MANIC.exe"; Description: "Launch MANIC"; Flags: nowait postinstall skipifsilent
