; PlanBench desktop installer.
;
; Built by scripts\build_desktop.ps1, which passes AppVersion, StageDir
; and OutputDir on the command line. Building this file by hand skips
; the smoke gate, which is the only thing that checks the packaging
; mechanisms the test suite cannot see — so don't.
;
; Two decisions here are worth the words:
;
; **Per-user, not Program Files.** This is a single-user application on a
; single machine. Installing under {localappdata} means no UAC prompt to
; install and none to update, and it removes a whole class of "works
; until it writes something" bugs — the installation directory is
; writable by the person using it.
;
; **The data directory is not ours to delete.** It holds a database of
; comparison runs somebody spent machine-hours producing. Uninstall asks
; rather than assumes, and the default answer is to keep it.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef StageDir
  #define StageDir "..\build\stage"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

[Setup]
; A fixed AppId is what makes the next version an upgrade rather than a
; second copy. Never regenerate it.
AppId={{7F1B4A62-3C9E-4E58-9E1D-2A6F0B5C8D31}
AppName=PlanBench
AppVersion={#AppVersion}
AppPublisher=PlanBench
DefaultDirName={localappdata}\Programs\PlanBench
DefaultGroupName=PlanBench
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
OutputDir={#OutputDir}
; No version in the file name, deliberately. The download link people
; are given is `/releases/latest/download/PlanBench-Setup.exe`, and that
; URL only stays valid while the asset keeps one stable name — a
; versioned name turns every release into a new link to hand out.
; The version lives inside the build (apps/desktop/.../VERSION), is
; reported on the System page, and is what the updater compares.
OutputBaseFilename=PlanBench-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=PlanBench
SetupIconFile=planbench.ico
UninstallDisplayIcon={app}\runtime\pythonw.exe
; Offer to close a running instance rather than writing over a locked
; file and leaving a half-upgraded installation behind.
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[InstallDelete]
; Wipe the previous code before writing the new one. An upgrade that
; renames or removes a module would otherwise leave the old file behind,
; importable and stale — and the data directory is untouched by this
; because it lives somewhere else entirely.
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\runtime"
Type: filesandordirs; Name: "{app}\web"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; pythonw.exe, not python.exe: the console window would otherwise flash
; on every launch, and every plugin subprocess would open one of its own.
Name: "{group}\PlanBench"; Filename: "{app}\runtime\pythonw.exe"; \
    Parameters: """{app}\app\apps\desktop\planbench_desktop\main.py"""; \
    WorkingDir: "{app}"; IconFilename: "{app}\planbench.ico"
Name: "{userdesktop}\PlanBench"; Filename: "{app}\runtime\pythonw.exe"; \
    Parameters: """{app}\app\apps\desktop\planbench_desktop\main.py"""; \
    WorkingDir: "{app}"; IconFilename: "{app}\planbench.ico"; Tasks: desktopicon
Name: "{group}\Uninstall PlanBench"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\runtime\pythonw.exe"; \
    Parameters: """{app}\app\apps\desktop\planbench_desktop\main.py"""; \
    Description: "Run PlanBench"; Flags: nowait postinstall skipifsilent

[Code]
function DataDirectory(): String;
begin
  Result := ExpandConstant('{localappdata}\PlanBench');
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Directory: String;
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;
  Directory := DataDirectory();
  if not DirExists(Directory) then
    Exit;
  { Asked, never assumed, and the default is No: this directory holds
    the database of comparison runs and the API key, and a run costs
    machine-hours to reproduce. }
  if MsgBox('Also delete PlanBench''s data?' + #13#10#13#10 +
            'This removes every comparison run, imported algorithm and setting in' + #13#10 +
            Directory + #13#10#13#10 +
            'Choose No to keep them for a future installation.',
            mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    DelTree(Directory, True, True, True);
end;
