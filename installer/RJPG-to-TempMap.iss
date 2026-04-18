; Inno Setup 6 installer script for R-JPG-to-TempMap.
;
; Requires a prior PyInstaller build: run build.bat first so that
; dist\RJPG-to-TempMap\ exists. Then compile this script with Inno Setup:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer\RJPG-to-TempMap.iss
;
; Output:
;   installer\Output\RJPG-to-TempMap-v2.0.0-setup.exe

#define MyAppName "R-JPG to TempMap"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "kincanek"
#define MyAppURL "https://github.com/kincanek/R-JPG-to-TempMap"
#define MyAppExeName "RJPG-to-TempMap.exe"

[Setup]
AppId={{3E59C5C0-8E1D-4D7C-BA58-4F2B0A8D5A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\RJPG-to-TempMap
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=RJPG-to-TempMap-v{#MyAppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Recursively pull in the whole PyInstaller onedir output.
Source: "..\dist\RJPG-to-TempMap\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
