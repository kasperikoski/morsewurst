#define MyAppName "Morsewurst"
#define MyAppVersion "0.99.7"
#define MyAppPublisher "Kasperi Koski"
#define MyAppExeName "Morsewurst.exe"

[Setup]
AppId={{f6ba2c5f-0a3f-4fac-80fb-13d81e2c3e45}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer
OutputBaseFilename=MorsewurstSetup_{#MyAppVersion}
SetupIconFile=Assets\morse.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
LicenseFile=license_fi.txt
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\{#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "finnish"; MessagesFile: "compiler:Languages\Finnish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Luo työpöytäkuvake"; GroupDescription: "Lisäkuvakkeet:"; Flags: unchecked

[Files]
Source: "dist\Morsewurst\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Poista {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Käynnistä {#MyAppName}"; Flags: nowait postinstall skipifsilent