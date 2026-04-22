; Inno Setup script for WinScanLLM.
;
; The AppId GUID below is stable FOREVER — if it changes between releases,
; existing installs won't be detected as upgrades and you get side-by-side
; installs. Do not regenerate it.
;
; Invoke locally:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=1.2.3 installer\WinScanLLM.iss
; Invoke in CI (release.yml):
;     & "$ISCC" /DAppVersion=$env:VERSION installer\WinScanLLM.iss

#define AppName "WinScanLLM"
#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{6BFB8149-100E-4A55-8A7A-18F87AABC3D7}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=aberrantCode
AppPublisherURL=https://github.com/aberrantCode/WinScanOllamaVision
AppSupportURL=https://github.com/aberrantCode/WinScanOllamaVision/issues
AppUpdatesURL=https://github.com/aberrantCode/WinScanOllamaVision/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
OutputDir=Output
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=force
RestartApplications=no
UninstallDisplayIcon={app}\{#AppName}.exe
SetupIconFile=..\assets\icon.ico
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\{#AppName}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}"; Filename: "{app}\{#AppName}.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppName}.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  AppDataDir: string;
begin
  // Ask whether to also remove user data, but ONLY in interactive uninstall.
  // During an in-place upgrade, Inno runs the old uninstaller silently —
  // UninstallSilent is True — and we must preserve user data unconditionally.
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    AppDataDir := ExpandConstant('{userappdata}\WinScanLLM');
    if DirExists(AppDataDir) then
    begin
      if MsgBox(
           'Also delete your WinScanLLM user data (settings, databases, logs) in:' + #13#10 +
           AppDataDir + #13#10 + #13#10 +
           'Choose No to keep your data for a future reinstall.',
           mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(AppDataDir, True, True, True);
      end;
    end;
  end;
end;
