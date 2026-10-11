; *** Inno Setup 6.5+ 简体中文消息（Violet 安装包专用） ***
;
; 安装向导里常见的几页（欢迎、选择位置、准备、完成、卸载）用了 Violet 的口吻；
; 报错类消息保持直白，方便看懂出了什么事。
; 英文原文里结尾没有句号的消息，这里也不加句号：Inno Setup 会自动补上。

[LangOptions]
LanguageName=简体中文
LanguageID=$0804
LanguageCodePage=936
DialogFontName=Microsoft YaHei UI
DialogFontSize=9
WelcomeFontName=Microsoft YaHei UI
WelcomeFontSize=14

[Messages]

; *** Application titles
SetupAppTitle=安装
SetupWindowTitle=安装 - %1
UninstallAppTitle=卸载
UninstallAppFullTitle=卸载 %1

; *** Misc. common
InformationTitle=信息
ConfirmTitle=确认
ErrorTitle=错误

; *** SetupLdr messages
SetupLdrStartupMessage=现在将安装 %1。要继续吗？
LdrCannotCreateTemp=无法创建临时文件，安装已中止
LdrCannotExecTemp=无法运行临时文件夹中的文件，安装已中止
HelpTextNote=

; *** Startup error messages
LastErrorMessage=%1。%n%n错误 %2：%3
SetupFileMissing=安装目录中缺少文件 %1。请修正这个问题，或重新获取一份安装程序。
SetupFileCorrupt=安装文件已损坏。请重新获取一份安装程序。
SetupFileCorruptOrWrongVer=安装文件已损坏，或与此版本的安装程序不兼容。请修正这个问题，或重新获取一份安装程序。
InvalidParameter=命令行中有无效的参数：%n%n%1
SetupAlreadyRunning=安装程序已经在运行。
WindowsVersionNotSupported=此程序不支持这台电脑上的 Windows 版本。
WindowsServicePackRequired=此程序需要 %1 Service Pack %2 或更高版本。
NotOnThisPlatform=此程序不能在 %1 上运行。
OnlyOnThisPlatform=此程序必须在 %1 上运行。
OnlyOnTheseArchitectures=此程序只能安装在为以下处理器架构设计的 Windows 上：%n%n%1
WinVersionTooLowError=此程序需要 %1 %2 或更高版本。
WinVersionTooHighError=此程序不能安装在 %1 %2 或更高版本上。
AdminPrivilegesRequired=安装此程序时必须以管理员身份登录。
PowerUserPrivilegesRequired=安装此程序时必须以管理员或 Power Users 组成员的身份登录。
SetupAppRunningError=%1 正在运行。%n%n请先关掉它（包括托盘里的图标），然后点「确定」继续，或点「取消」退出。
UninstallAppRunningError=%1 正在运行。%n%n请先关掉它（包括托盘里的图标），然后点「确定」继续，或点「取消」退出。

; *** Startup questions
PrivilegesRequiredOverrideTitle=选择安装方式
PrivilegesRequiredOverrideInstruction=选择安装方式
PrivilegesRequiredOverrideText1=%1 可以为这台电脑上的所有用户安装（需要管理员权限），也可以只为你安装。
PrivilegesRequiredOverrideText2=%1 可以只为你安装，也可以为这台电脑上的所有用户安装（需要管理员权限）。
PrivilegesRequiredOverrideAllUsers=为所有用户安装(&A)
PrivilegesRequiredOverrideAllUsersRecommended=为所有用户安装（推荐）(&A)
PrivilegesRequiredOverrideCurrentUser=只为我安装(&M)
PrivilegesRequiredOverrideCurrentUserRecommended=只为我安装（推荐）(&M)

; *** Misc. errors
ErrorCreatingDir=无法创建文件夹“%1”
ErrorTooManyFilesInDir=文件夹“%1”中的文件太多，无法再创建文件

; *** Setup common messages
ExitSetupTitle=退出安装
ExitSetupMessage=还没有安装完。如果现在退出，程序不会被安装。%n%n以后可以再运行安装程序来完成安装。%n%n要退出吗？
AboutSetupMenuItem=关于安装程序(&A)...
AboutSetupTitle=关于安装程序
AboutSetupMessage=%1 版本 %2%n%3%n%n%1 主页：%n%4
AboutSetupNote=
TranslatorNote=

; *** Buttons
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonOK=确定
ButtonCancel=取消
ButtonYes=是(&Y)
ButtonYesToAll=全部是(&A)
ButtonNo=否(&N)
ButtonNoToAll=全部否(&O)
ButtonFinish=完成(&F)
ButtonBrowse=浏览(&B)...
ButtonWizardBrowse=浏览(&R)...
ButtonNewFolder=新建文件夹(&M)

; *** "Select Language" dialog messages
SelectLanguageTitle=选择安装语言
SelectLanguageLabel=选择安装时使用的语言。

; *** Common wizard text
ClickNext=点「下一步」继续，或点「取消」退出安装。
BeveledLabel=
BrowseDialogTitle=浏览文件夹
BrowseDialogLabel=在下面的列表中选一个文件夹，然后点「确定」。
NewFolderName=新建文件夹

; *** "Welcome" wizard page
WelcomeLabel1=你好，我是 Violet
WelcomeLabel2=接下来会把 [name/ver] 安放在这台电脑上。%n%n我会替你寻歌、收信、整理书信匣，也会在书桌上陪你写字。%n%n继续之前，最好先关掉其他正在运行的程序。

; *** "Password" wizard page
WizardPassword=密码
PasswordLabel1=这个安装程序受密码保护。
PasswordLabel3=请输入密码，然后点「下一步」继续。密码区分大小写。
PasswordEditLabel=密码(&P)：
IncorrectPassword=密码不对，请再试一次。

; *** "License Agreement" wizard page
WizardLicense=许可协议
LicenseLabel=继续之前，请先读一读下面的重要信息。
LicenseLabel3=请阅读下面的许可协议。接受协议条款后才能继续安装。
LicenseAccepted=我接受协议(&A)
LicenseNotAccepted=我不接受协议(&D)

; *** "Information" wizard pages
WizardInfoBefore=信息
InfoBeforeLabel=继续之前，请先读一读下面的重要信息。
InfoBeforeClickLabel=准备好继续安装后，点「下一步」。
WizardInfoAfter=信息
InfoAfterLabel=继续之前，请先读一读下面的重要信息。
InfoAfterClickLabel=准备好继续安装后，点「下一步」。

; *** "User Information" wizard page
WizardUserInfo=用户信息
UserInfoDesc=请填写你的信息。
UserInfoName=用户名(&U)：
UserInfoOrg=单位(&O)：
UserInfoSerial=序列号(&S)：
UserInfoNameRequired=必须填写用户名。

; *** "Select Destination Location" wizard page
WizardSelectDir=选择安装位置
SelectDirDesc=要把 [name] 安放在哪里？
SelectDirLabel3=[name] 会被安放在下面这个文件夹里。
SelectDirBrowseLabel=点「下一步」继续。如果想换一个文件夹，点「浏览」。
DiskSpaceGBLabel=至少需要 [gb] GB 的可用磁盘空间。
DiskSpaceMBLabel=至少需要 [mb] MB 的可用磁盘空间。
CannotInstallToNetworkDrive=不能安装到网络驱动器上。
CannotInstallToUNCPath=不能安装到 UNC 路径上。
InvalidPath=请输入带盘符的完整路径，例如：%n%nC:\APP%n%n或下面这种格式的 UNC 路径：%n%n\\server\share
InvalidDrive=所选的驱动器或 UNC 共享不存在或无法访问，请另选一个。
DiskSpaceWarningTitle=磁盘空间不足
DiskSpaceWarning=安装至少需要 %1 KB 的可用空间，但所选驱动器只有 %2 KB。%n%n仍然要继续吗？
DirNameTooLong=文件夹名称或路径太长。
InvalidDirName=文件夹名称无效。
BadDirName32=文件夹名称不能包含以下字符：%n%n%1
DirExistsTitle=文件夹已存在
DirExists=文件夹：%n%n%1%n%n已经存在。仍然要安装到这个文件夹吗？
DirDoesntExistTitle=文件夹不存在
DirDoesntExist=文件夹：%n%n%1%n%n不存在。要创建它吗？

; *** "Select Components" wizard page
WizardSelectComponents=选择组件
SelectComponentsDesc=要安装哪些组件？
SelectComponentsLabel2=勾选要安装的组件，取消勾选不需要的组件。准备好后点「下一步」。
FullInstallation=完整安装
CompactInstallation=精简安装
CustomInstallation=自定义安装
NoUninstallWarningTitle=组件已存在
NoUninstallWarning=这台电脑上已经装有以下组件：%n%n%1%n%n取消勾选不会卸载它们。%n%n仍然要继续吗？
ComponentSize1=%1 KB
ComponentSize2=%1 MB
ComponentsDiskSpaceGBLabel=当前选择至少需要 [gb] GB 的磁盘空间。
ComponentsDiskSpaceMBLabel=当前选择至少需要 [mb] MB 的磁盘空间。

; *** "Select Additional Tasks" wizard page
WizardSelectTasks=还有几件小事
SelectTasksDesc=要顺便做些什么？
SelectTasksLabel2=选好安装 [name] 时要顺便做的事，然后点「下一步」。

; *** "Select Start Menu Folder" wizard page
WizardSelectProgramGroup=选择开始菜单文件夹
SelectStartMenuFolderDesc=要把程序的快捷方式放在哪里？
SelectStartMenuFolderLabel3=快捷方式会放在下面这个开始菜单文件夹里。
SelectStartMenuFolderBrowseLabel=点「下一步」继续。如果想换一个文件夹，点「浏览」。
MustEnterGroupName=必须填写文件夹名称。
GroupNameTooLong=文件夹名称或路径太长。
InvalidGroupName=文件夹名称无效。
BadGroupName=文件夹名称不能包含以下字符：%n%n%1
NoProgramGroupCheck2=不创建开始菜单文件夹(&D)

; *** "Ready to Install" wizard page
WizardReady=准备好了
ReadyLabel1=一切就绪，可以把 [name] 安放到这台电脑上了。
ReadyLabel2a=点「安装」开始；想再看看或改改设置，点「上一步」。
ReadyLabel2b=点「安装」开始。
ReadyMemoUserInfo=用户信息：
ReadyMemoDir=安装位置：
ReadyMemoType=安装类型：
ReadyMemoComponents=所选组件：
ReadyMemoGroup=开始菜单文件夹：
ReadyMemoTasks=顺便要做的事：

; *** TDownloadWizardPage wizard page and DownloadTemporaryFile
DownloadingLabel2=正在下载文件...
ButtonStopDownload=停止下载(&S)
StopDownload=确定要停止下载吗？
ErrorDownloadAborted=下载已中止
ErrorDownloadFailed=下载失败：%1 %2
ErrorDownloadSizeFailed=获取大小失败：%1 %2
ErrorProgress=进度无效：%1 / %2
ErrorFileSize=文件大小不对：应为 %1，实际为 %2

; *** TExtractionWizardPage wizard page and ExtractArchive
ExtractingLabel=正在解压文件...
ButtonStopExtraction=停止解压(&S)
StopExtraction=确定要停止解压吗？
ErrorExtractionAborted=解压已中止
ErrorExtractionFailed=解压失败：%1

; *** Archive extraction failure details
ArchiveIncorrectPassword=密码不对
ArchiveIsCorrupted=压缩包已损坏
ArchiveUnsupportedFormat=不支持这种压缩包格式

; *** "Preparing to Install" wizard page
WizardPreparing=正在准备
PreparingDesc=正在准备把 [name] 安放到这台电脑上。
PreviousInstallNotCompleted=之前某个程序的安装或卸载还没有完成，需要重启电脑才能完成。%n%n重启后，请再次运行安装程序来完成 [name] 的安装。
CannotContinue=安装无法继续。请点「取消」退出。
ApplicationsFound=下列程序正在使用需要更新的文件。建议让安装程序自动关闭它们。
ApplicationsFound2=下列程序正在使用需要更新的文件。建议让安装程序自动关闭它们。安装完成后，安装程序会尝试重新打开它们。
CloseApplications=自动关闭这些程序(&A)
DontCloseApplications=不关闭这些程序(&D)
ErrorCloseApplications=安装程序没能自动关闭所有程序。建议先手动关闭正在使用待更新文件的程序，再继续。
PrepareToInstallNeedsRestart=需要重启电脑。重启后，请再次运行安装程序来完成 [name] 的安装。%n%n现在重启吗？

; *** "Installing" wizard page
WizardInstalling=正在安装
InstallingLabel=请稍候，正在把 [name] 安放到这台电脑上。

; *** "Setup Completed" wizard page
FinishedHeadingLabel=[name] 已经到了
FinishedLabelNoIcons=[name] 已经安装好了。
FinishedLabel=[name] 已经安装好了。以后可以从开始菜单或桌面上的快捷方式找到她。
ClickFinish=点「完成」关上这个窗口。
FinishedRestartLabel=要完成 [name] 的安装，需要重启电脑。现在重启吗？
FinishedRestartMessage=要完成 [name] 的安装，需要重启电脑。%n%n现在重启吗？
ShowReadmeCheck=是的，我想看看说明文件
YesRadio=是，现在重启电脑(&Y)
NoRadio=否，稍后再重启(&N)
RunEntryExec=打开 %1
RunEntryShellExec=查看 %1

; *** "Setup Needs the Next Disk" stuff
ChangeDiskTitle=需要下一张磁盘
SelectDiskLabel2=请插入第 %1 张磁盘，然后点「确定」。%n%n如果这张磁盘上的文件在下面显示的文件夹以外的位置，请输入正确的路径或点「浏览」。
PathLabel=路径(&P)：
FileNotInDir2=在“%2”中找不到文件“%1”。请插入正确的磁盘或另选一个文件夹。
SelectDirectoryLabel=请指定下一张磁盘的位置。

; *** Installation phase messages
SetupAborted=安装没有完成。%n%n请修正问题后再次运行安装程序。
AbortRetryIgnoreSelectAction=选择操作
AbortRetryIgnoreRetry=重试(&T)
AbortRetryIgnoreIgnore=忽略错误并继续(&I)
AbortRetryIgnoreCancel=取消安装
RetryCancelSelectAction=选择操作
RetryCancelRetry=重试(&T)
RetryCancelCancel=取消

; *** Installation status messages
StatusClosingApplications=正在关闭程序...
StatusCreateDirs=正在创建文件夹...
StatusExtractFiles=正在放好文件...
StatusDownloadFiles=正在下载文件...
StatusCreateIcons=正在创建快捷方式...
StatusCreateIniEntries=正在写入 INI 项...
StatusCreateRegistryEntries=正在写入注册表项...
StatusRegisterFiles=正在注册文件...
StatusSavingUninstall=正在保存卸载信息...
StatusRunProgram=正在完成安装...
StatusRestartingApplications=正在重新打开程序...
StatusRollback=正在撤销更改...

; *** Misc. errors
ErrorInternal2=内部错误：%1
ErrorFunctionFailedNoCode=%1 失败
ErrorFunctionFailed=%1 失败；代码 %2
ErrorFunctionFailedWithMessage=%1 失败；代码 %2。%n%3
ErrorExecutingProgram=无法运行文件：%n%1

; *** Registry errors
ErrorRegOpenKey=打开注册表项时出错：%n%1\%2
ErrorRegCreateKey=创建注册表项时出错：%n%1\%2
ErrorRegWriteKey=写入注册表项时出错：%n%1\%2

; *** INI errors
ErrorIniEntry=在文件“%1”中创建 INI 项时出错。

; *** File copying errors
FileAbortRetryIgnoreSkipNotRecommended=跳过这个文件（不推荐）(&S)
FileAbortRetryIgnoreIgnoreNotRecommended=忽略错误并继续（不推荐）(&I)
SourceIsCorrupted=源文件已损坏
SourceDoesntExist=源文件“%1”不存在
SourceVerificationFailed=源文件校验失败：%1
VerificationSignatureDoesntExist=签名文件“%1”不存在
VerificationSignatureInvalid=签名文件“%1”无效
VerificationKeyNotFound=签名文件“%1”使用了未知的密钥
VerificationFileNameIncorrect=文件名不对
VerificationFileTagIncorrect=文件标签不对
VerificationFileSizeIncorrect=文件大小不对
VerificationFileHashIncorrect=文件哈希不对
ExistingFileReadOnly2=现有文件是只读的，无法替换。
ExistingFileReadOnlyRetry=去掉只读属性后重试(&R)
ExistingFileReadOnlyKeepExisting=保留现有文件(&K)
ErrorReadingExistingDest=读取现有文件时出错：
FileExistsSelectAction=选择操作
FileExists2=文件已经存在。
FileExistsOverwriteExisting=覆盖现有文件(&O)
FileExistsKeepExisting=保留现有文件(&K)
FileExistsOverwriteOrKeepAll=之后遇到同样的情况也这样处理(&D)
ExistingFileNewerSelectAction=选择操作
ExistingFileNewer2=现有文件比要安装的文件更新。
ExistingFileNewerOverwriteExisting=覆盖现有文件(&O)
ExistingFileNewerKeepExisting=保留现有文件（推荐）(&K)
ExistingFileNewerOverwriteOrKeepAll=之后遇到同样的情况也这样处理(&D)
ErrorChangingAttr=修改现有文件的属性时出错：
ErrorCreatingTemp=在安装文件夹中创建文件时出错：
ErrorReadingSource=读取源文件时出错：
ErrorCopying=复制文件时出错：
ErrorDownloading=下载文件时出错：
ErrorExtracting=解压时出错：
ErrorReplacingExistingFile=替换现有文件时出错：
ErrorRestartReplace=重启后替换失败：
ErrorRenamingTemp=在安装文件夹中重命名文件时出错：
ErrorRegisterServer=无法注册 DLL/OCX：%1
ErrorRegSvr32Failed=RegSvr32 失败，退出代码 %1
ErrorRegisterTypeLib=无法注册类型库：%1

; *** Uninstall display name markings
UninstallDisplayNameMark=%1（%2）
UninstallDisplayNameMarks=%1（%2，%3）
UninstallDisplayNameMark32Bit=32 位
UninstallDisplayNameMark64Bit=64 位
UninstallDisplayNameMarkAllUsers=所有用户
UninstallDisplayNameMarkCurrentUser=当前用户

; *** Post-installation errors
ErrorOpeningReadme=打开说明文件时出错。
ErrorRestartingComputer=安装程序无法重启电脑，请手动重启。

; *** Uninstaller messages
UninstallNotFound=文件“%1”不存在，无法卸载。
UninstallOpenError=无法打开文件“%1”，无法卸载
UninstallUnsupportedVer=这个版本的卸载程序无法识别卸载日志“%1”的格式，无法卸载
UninstallUnknownEntry=卸载日志中有未知的条目（%1）
ConfirmUninstall=确定要把 %1 从这台电脑上移除吗？%n%n你下载的歌不会被删除。
UninstallOnlyOnWin64=只能在 64 位 Windows 上卸载。
OnlyAdminCanUninstall=只有具有管理员权限的用户才能卸载。
UninstallStatusLabel=请稍候，正在把 %1 从这台电脑上移除。
UninstalledAll=%1 已经从这台电脑上移除了。谢谢你陪我走过这一段。
UninstalledMost=%1 已卸载。%n%n有些项目没能移除，可以手动删除。
UninstalledAndNeedsRestart=要完成 %1 的卸载，需要重启电脑。%n%n现在重启吗？
UninstallDataCorrupted=文件“%1”已损坏，无法卸载

; *** Uninstallation phase messages
ConfirmDeleteSharedFileTitle=删除共享文件？
ConfirmDeleteSharedFile2=系统显示下面这个共享文件已经没有程序在用了。要删除它吗？%n%n如果仍有程序在用它，删除后那些程序可能无法正常工作。拿不准的话请选「否」，留着它不会有任何害处。
SharedFileNameLabel=文件名：
SharedFileLocationLabel=位置：
WizardUninstalling=卸载状态
StatusUninstalling=正在卸载 %1...

; *** Shutdown block reasons
ShutdownBlockReasonInstallingApp=正在安装 %1。
ShutdownBlockReasonUninstallingApp=正在卸载 %1。

[CustomMessages]

NameAndVersion=%1 版本 %2
AdditionalIcons=快捷方式：
CreateDesktopIcon=在桌面上放一个快捷方式(&D)
CreateQuickLaunchIcon=创建快速启动栏快捷方式(&Q)
ProgramOnTheWeb=%1 网站
UninstallProgram=卸载 %1
LaunchProgram=打开 %1
AssocFileExtension=将 %1 与 %2 文件扩展名关联(&A)
AssocingFileExtension=正在将 %1 与 %2 文件扩展名关联...
AutoStartProgramGroupDescription=启动：
AutoStartProgram=开机时自动启动 %1
AddonHostProgramNotFound=在所选文件夹中找不到 %1。%n%n仍然要继续吗？
