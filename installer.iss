; Inno Setup script for Lumina Control

[Setup]
AppName=Lumina Control
AppVersion=1.2.9
AppPublisher=Nicolas Gounot
DefaultDirName={pf}\Lumina Control
DefaultGroupName=Lumina Control
UninstallDisplayIcon={app}\LuminaControl.exe
OutputDir=dist-installer
OutputBaseFilename=LuminaControlSetup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
SetupIconFile=icon.ico

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\LuminaControl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Lumina Control"; Filename: "{app}\LuminaControl.exe"; IconFilename: "{app}\icon.ico"
Name: "{commondesktop}\Lumina Control"; Filename: "{app}\LuminaControl.exe"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\LuminaControl.exe"; Description: "Launch Lumina Control"; Flags: nowait postinstall skipifsilent
