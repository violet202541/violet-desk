; Violet 安装包（Inno Setup 6.5+）。用 tools\build_setup.bat 生成 dist\Violet-Setup-<版本>.exe。
; 默认只为当前用户安装（不需要管理员权限），也可以在开头选为所有用户安装。
; 个人数据在 %APPDATA%\Violet，歌在“音乐\Violet”；卸载时只问一次要不要清掉个人数据，歌永远不动。

#ifndef AppVersion
  #define AppVersion "0.0"
#endif
#define Root "..\.."
#define Art Root + "\build\installer"
#define Sizes(Kind, Theme) \
  Art + "\" + Kind + "-" + Theme + "-100.png," + Art + "\" + Kind + "-" + Theme + "-125.png," + \
  Art + "\" + Kind + "-" + Theme + "-150.png," + Art + "\" + Kind + "-" + Theme + "-175.png," + \
  Art + "\" + Kind + "-" + Theme + "-200.png," + Art + "\" + Kind + "-" + Theme + "-250.png"

[Setup]
AppId={{B5565AAC-1869-4C9C-B274-33A19ADB36B8}
AppName=Violet
AppVersion={#AppVersion}
AppVerName=Violet {#AppVersion}
AppPublisher=Violet
AppCopyright=Violet
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Violet 安装程序
DefaultDirName={autopf}\Violet
DisableProgramGroupPage=yes
DisableWelcomePage=no
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
AppMutex=VioletRunning
CloseApplications=yes
RestartApplications=no
OutputDir={#Root}\dist
OutputBaseFilename=Violet-Setup-{#AppVersion}
SetupIconFile={#Root}\tools\violet.ico
UninstallDisplayIcon={app}\Violet.exe
UninstallDisplayName=Violet
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern dynamic windows11
WizardBackColor=#f3ecdf
WizardBackColorDynamicDark=#16131d
WizardImageFile={#Sizes("wizard", "light")}
WizardImageFileDynamicDark={#Sizes("wizard", "dark")}
WizardSmallImageFile={#Sizes("small", "light")}
WizardSmallImageFileDynamicDark={#Sizes("small", "dark")}
WizardSmallImageBackColor=#f3ecdf
WizardSmallImageBackColorDynamicDark=#16131d

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl,ChineseSimplified.isl"

[CustomMessages]
chinesesimp.WebView2Missing=Violet 的窗口要用到 Microsoft Edge WebView2 运行库，这台电脑上好像还没有。%n%n要现在打开微软的下载页吗？装好后再打开 Violet 就行。
chinesesimp.KeepPersonalData=Violet 已经移除了。%n%n要不要连同你的信件、日记、压花、信札和设置一起清掉？%n%n选「否」会把它们留着，以后重新安装时会原样回来。你下载的歌在“音乐\Violet”里，无论选哪个都不会被删除。

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Upgrades replace the whole runtime folder, so files dropped by a newer PyInstaller never mix with old ones.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Root}\dist\Violet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Violet"; Filename: "{app}\Violet.exe"; Comment: "音乐、书信与书桌"
Name: "{autodesktop}\Violet"; Filename: "{app}\Violet.exe"; Comment: "音乐、书信与书桌"; Tasks: desktopicon

[Run]
Filename: "{app}\Violet.exe"; Description: "现在就打开 Violet"; Flags: nowait postinstall skipifsilent

[Code]
const
  WebView2Client = 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Page = 'https://developer.microsoft.com/microsoft-edge/webview2/';

function HasVersion(Root: Integer; Key: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function WebView2Installed: Boolean;
begin
  Result := HasVersion(HKLM32, WebView2Client) or HasVersion(HKCU, WebView2Client);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
begin
  if (CurStep = ssPostInstall) and not WizardSilent and not WebView2Installed then
    if MsgBox(CustomMessage('WebView2Missing'), mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', WebView2Page, '', '', SW_SHOWNORMAL, ewNoWait, Code);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
    if MsgBox(CustomMessage('KeepPersonalData'), mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
    begin
      DelTree(ExpandConstant('{userappdata}\Violet'), True, True, True);
      DelTree(ExpandConstant('{%USERPROFILE}\.violet_webview'), True, True, True);
    end;
end;
