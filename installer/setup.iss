; =====================================================================
; Musicat - Inno Setup Script
; Generates dual-mode standalone installer: Standard (PC) or Portable (USB)
; Target Repo: https://github.com/IlRed89/Musicat
; =====================================================================

#define MyAppName "Musicat"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "IlRed89"
#define MyAppURL "https://github.com/IlRed89/Musicat"
#define MyAppExeName "Musicat.exe"

[Setup]
AppId={{D37F8A12-88E2-4D93-9F1C-7F10E0B49C89}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\dist
OutputBaseFilename=Musicat-Setup-Windows-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=auto
PrivilegesRequiredOverridesAllowed=commandline dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; Check: IsStandardMode

[Files]
; Primary application binaries from PyInstaller dist
Source: "..\dist\Musicat\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Check: IsStandardMode
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; Check: IsStandardMode
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Check: IsStandardMode

[Registry]
; Standard mode: register app in CurrentUser or LocalMachine
Root: HKA; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey; Check: IsStandardMode
Root: HKA; Subkey: "Software\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallMode"; ValueData: "Standard"; Flags: uninsdeletekey; Check: IsStandardMode

[Code]
var
  InstallModePage: TWizardPage;
  StandardRadio: TRadioButton;
  PortableRadio: TRadioButton;
  ModeDescLabel: TLabel;

// Detect whether Standard Mode was selected
function IsStandardMode(): Boolean;
begin
  Result := (StandardRadio <> nil) and (StandardRadio.Checked);
end;

// Detect whether Portable Mode was selected
function IsPortableMode(): Boolean;
begin
  Result := (PortableRadio <> nil) and (PortableRadio.Checked);
end;

procedure ModeRadioClick(Sender: TObject);
begin
  if StandardRadio.Checked then
  begin
    ModeDescLabel.Caption :=
      'Modalità Standard:' + #13#10 +
      '• Installa in Program Files (o cartella di sistema).' + #13#10 +
      '• Crea collegamenti sul Desktop e nel Menu Start.' + #13#10 +
      '• Configurazione e database salvati in %APPDATA%\Musicat.';
    WizardForm.DirEdit.Text := ExpandConstant('{autopf}\Musicat');
  end
  else
  begin
    ModeDescLabel.Caption :=
      'Modalità Portatile:' + #13#10 +
      '• Estrae Musicat in una cartella autonoma (es. disco esterno USB o SD).' + #13#10 +
      '• Crea il file portable.lock: dati, SQLite e log risiedono SOLO nella cartella locale.' + #13#10 +
      '• Nessuna voce di registro o disinstallatore di sistema creato.';
    WizardForm.DirEdit.Text := 'C:\Musicat_Portable';
  end;
end;

procedure InitializeWizard;
var
  PromptLabel: TLabel;
begin
  // Create Custom Page after Welcome Page
  InstallModePage := CreateCustomPage(wpWelcome, 'Seleziona Modalità di Installazione', 'Scegli come installare e configurare Musicat');

  PromptLabel := TLabel.Create(InstallModePage);
  PromptLabel.Parent := InstallModePage.Surface;
  PromptLabel.Caption := 'Scegli la modalità più adatta alle tue esigenze:';
  PromptLabel.Left := ScaleX(0);
  PromptLabel.Top := ScaleY(10);
  PromptLabel.Font.Style := [fsBold];

  StandardRadio := TRadioButton.Create(InstallModePage);
  StandardRadio.Parent := InstallModePage.Surface;
  StandardRadio.Caption := 'Installazione Standard (Computer Fisso / Laptop principale)';
  StandardRadio.Left := ScaleX(10);
  StandardRadio.Top := ScaleY(40);
  StandardRadio.Width := ScaleX(450);
  StandardRadio.Checked := True;
  StandardRadio.OnClick := @ModeRadioClick;

  PortableRadio := TRadioButton.Create(InstallModePage);
  PortableRadio.Parent := InstallModePage.Surface;
  PortableRadio.Caption := 'Installazione Portatile (Pendrive / SSD Esterno per DJ)';
  PortableRadio.Left := ScaleX(10);
  PortableRadio.Top := ScaleY(70);
  PortableRadio.Width := ScaleX(450);
  PortableRadio.OnClick := @ModeRadioClick;

  ModeDescLabel := TLabel.Create(InstallModePage);
  ModeDescLabel.Parent := InstallModePage.Surface;
  ModeDescLabel.Left := ScaleX(20);
  ModeDescLabel.Top := ScaleY(110);
  ModeDescLabel.Width := ScaleX(440);
  ModeDescLabel.Height := ScaleY(90);
  ModeDescLabel.WordWrap := True;

  ModeRadioClick(nil);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  LockFile: String;
begin
  if CurStep = ssPostInstall then
  begin
    LockFile := ExpandConstant('{app}\portable.lock');
    if IsPortableMode() then
    begin
      // Create portable.lock flag file
      SaveStringToFile(LockFile, 'musicat_portable_mode=true' + #13#10 + 'created=' + GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':'), False);
    end
    else
    begin
      // Ensure portable.lock does not exist in standard mode
      if FileExists(LockFile) then
        DeleteFile(LockFile);
    end;
  end;
end;
