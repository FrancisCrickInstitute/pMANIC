[Setup]
AppName=MANIC
AppVersion=4.0.0
DefaultDirName={pf}\MANIC
DefaultGroupName=MANIC
OutputDir=..\dist
OutputBaseFilename=MANIC-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
DisableDirPage=no
DisableProgramGroupPage=no

[Files]
Source: "..\\dist\\MANIC\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\MANIC"; Filename: "{app}\MANIC.exe"
Name: "{commondesktop}\MANIC"; Filename: "{app}\MANIC.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\MANIC.exe"; Description: "Launch MANIC"; Flags: nowait postinstall skipifsilent
