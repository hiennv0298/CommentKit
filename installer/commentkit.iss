; Inno Setup 6 script for CommentKit. Built by scripts\build.ps1 after PyInstaller.
; Installs per user (no admin) into %LOCALAPPDATA%\Programs\CommentKit.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{990CB19B-DF9B-48A3-AA79-C9D7BA41E33B}
AppName=CommentKit
AppVersion={#AppVersion}
AppPublisher=hiennv0298
AppComments=Make funny-comments YouTube Shorts from Threads screenshots (AI script + VieNeu voices + FFmpeg)
DefaultDirName={localappdata}\Programs\CommentKit
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=CommentKit-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesEnvironment=yes
WizardStyle=modern
SetupIconFile=..\src\commentkit\webui\commentkit.ico
UninstallDisplayIcon={app}\CommentKitApp.exe
UninstallDisplayName=CommentKit
; CommentKitApp.exe runs without a window of its own (the window is Edge), so Windows cannot ask it to
; close, and a silent upgrade would abort with "unable to automatically close all applications".
; PrepareToInstall below waits for CommentKit to quit by itself; force closes whatever is still left.
CloseApplications=force

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "addtopath"; Description: "Add CommentKit to PATH (lets you type 'commentkit' in cmd)"; GroupDescription: "Command line:"

[Files]
Source: "..\dist\CommentKit\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\CommentKit"; Filename: "{app}\CommentKitApp.exe"; AppUserModelID: "hiennv0298.CommentKit"
Name: "{autodesktop}\CommentKit"; Filename: "{app}\CommentKitApp.exe"; AppUserModelID: "hiennv0298.CommentKit"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; \
  ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
Filename: "{app}\CommentKitApp.exe"; Description: "Open CommentKit now"; Flags: postinstall nowait skipifsilent
; Run with /VERYSILENT /RELAUNCH=1 (scripted upgrade): reopen CommentKit when done.
Filename: "{app}\CommentKitApp.exe"; Flags: nowait; Check: RelaunchRequested

[Code]
function RelaunchRequested: Boolean;
begin
  Result := ExpandConstant('{param:relaunch|0}') = '1';
end;

{ How many CommentKit processes (the app, the command line, its FFmpeg) run from the install folder. }
function RunningFromApp(): Integer;
var
  Locator, Service, Items, Item: Variant;
  Dir, Path: String;
  I: Integer;
begin
  Result := 0;
  Dir := Lowercase(AddBackslash(ExpandConstant('{app}')));
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Items := Service.ExecQuery('SELECT ExecutablePath FROM Win32_Process WHERE Name = ''CommentKitApp.exe'' ' +
                               'OR Name = ''commentkit.exe'' OR Name = ''ffmpeg.exe'' OR Name = ''ffprobe.exe''');
    for I := 0 to Items.Count - 1 do
    begin
      Item := Items.ItemIndex(I);
      if not VarIsNull(Item.ExecutablePath) then
      begin
        Path := Item.ExecutablePath;
        Path := Lowercase(Path);
        if Copy(Path, 1, Length(Dir)) = Dir then
          Result := Result + 1;
      end;
    end;
  except
    Result := 0;  { no WMI: leave it to CloseApplications=force }
  end;
end;

{ When CommentKit is still finishing a video, wait for it to quit (up to 15 s)
  instead of failing on files in use. Runs before Setup checks for applications using the files. }
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  I: Integer;
begin
  Result := '';
  for I := 1 to 30 do
  begin
    if RunningFromApp() = 0 then
      Break;
    Log(Format('Waiting for CommentKit to quit (%d)', [I]));
    Sleep(500);
  end;
end;

function NeedsAddPath(Dir: string): Boolean;
var
  Paths: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Paths) then
  begin
    Result := True;
    exit;
  end;
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') = 0;
end;

procedure RemoveFromPath(Dir: string);
var
  Paths: string;
  P: Integer;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Paths) then
    exit;
  P := Pos(';' + Uppercase(Dir), Uppercase(Paths));
  if P > 0 then
  begin
    Delete(Paths, P, Length(Dir) + 1);
    RegWriteExpandStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Paths);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
