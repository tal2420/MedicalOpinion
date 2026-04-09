; Inno Setup Script for Medical Opinion Management App
; Requires Inno Setup 6.x (https://jrsoftware.org/isinfo.php)

#define MyAppName "Medical Opinion Manager"
#define MyAppNameHeb "ניהול חוות דעת רפואיות"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Medical Opinion"
#define MyAppExeName "MedicalOpinion.exe"

[Setup]
AppId={{8F2E4A5B-3C1D-4E6F-9A8B-7C2D1E3F4A5B}
AppName={#MyAppNameHeb}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppNameHeb}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=MedicalOpinion_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "hebrew"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "צור קיצור דרך בשולחן העבודה"; GroupDescription: "קיצורי דרך:"

[Files]
Source: "dist\MedicalOpinion\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppNameHeb}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\הסר התקנה"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppNameHeb}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "הפעל את האפליקציה"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\__pycache__"
