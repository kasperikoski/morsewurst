$ErrorActionPreference = "Stop"

Write-Host "=== Morsewurst Windows build ==="

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$IconPath = Join-Path $ProjectRoot "Assets\morse.ico"
$InstallerScript = Join-Path $ProjectRoot "installer.iss"

Write-Host "Checking required files..."

$RequiredFiles = @(
    "main.py",
    "requirements.txt",
    "installer.iss",
    "installer.iss",
    "Assets\morse.ico",
    "Assets\img\startup_screen.png",
    "Assets\img\network_startup_screen.png",
    "morsewurst\ui\network\__init__.py",
    "morsewurst\ui\network\lobby_window.py",
    "morsewurst\ui\network\lobby_state.py",
    "morsewurst\ui\network\lobby_actions.py",
    "morsewurst\ui\network\server_queries.py",
    "morsewurst\ui\network\startup_screen.py",
    "morsewurst\ui\network\startup_sequence.py",
    "morsewurst\ui\network\widgets.py",
    "morsewurst\ui\network\views\__init__.py",
    "morsewurst\ui\network\views\callsign_view.py",
    "morsewurst\ui\network\views\lobby_view.py",
    "morsewurst\ui\network\views\room_view.py",
    "morsewurst\ui\network\views\settings_view.py",
    "morsewurst\ui\network\views\server_info_view.py",
    "morsewurst\ui\network_matrix_theme.py",
    "morsewurst\network\public_rooms.py",
    "morsewurst\network\settings_store.py",
    "morsewurst\network\defaults.py"
)

foreach ($File in $RequiredFiles) {
    if (!(Test-Path (Join-Path $ProjectRoot $File))) {
        throw "Required file was not found: $File"
    }
}

Write-Host "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install --upgrade pyinstaller

Write-Host "Cleaning previous build files..."
Remove-Item -Recurse -Force "build" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue
Remove-Item -Force "Morsewurst.spec" -ErrorAction SilentlyContinue

Write-Host "Building PyInstaller folder package..."

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name Morsewurst `
    --icon "$IconPath" `
    --collect-all morsewurst `
    --collect-all websockets `
    --collect-all sounddevice `
    --hidden-import morsewurst.ui.network `
    --hidden-import morsewurst.ui.network.lobby_window `
    --hidden-import morsewurst.ui.network.lobby_state `
    --hidden-import morsewurst.ui.network.lobby_actions `
    --hidden-import morsewurst.ui.network.server_queries `
    --hidden-import morsewurst.ui.network.startup_screen `
    --hidden-import morsewurst.ui.network.startup_sequence `
    --hidden-import morsewurst.ui.network.widgets `
    --hidden-import morsewurst.ui.network.views.callsign_view `
    --hidden-import morsewurst.ui.network.views.lobby_view `
    --hidden-import morsewurst.ui.network.views.room_view `
    --hidden-import morsewurst.ui.network.views.settings_view `
    --hidden-import morsewurst.ui.network.views.server_info_view `
    --hidden-import morsewurst.ui.network_matrix_theme `
    --hidden-import morsewurst.network.public_rooms `
    --hidden-import morsewurst.network.settings_store `
    --hidden-import morsewurst.core.morse_preview_player `
    --add-data "Assets;Assets" `
    main.py

$ExePath = Join-Path $ProjectRoot "dist\Morsewurst\Morsewurst.exe"

if (!(Test-Path $ExePath)) {
    throw "Build failed. EXE was not created: $ExePath"
}

Write-Host "PyInstaller build created:"
Write-Host $ExePath

Write-Host "Testing built EXE exists and package folder was created..."

if (!(Test-Path (Join-Path $ProjectRoot "dist\Morsewurst"))) {
    throw "dist\Morsewurst folder was not created."
}

Write-Host "Looking for Inno Setup..."

$InnoCompilerCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 7\ISCC.exe"
)

$InnoCompiler = $null

foreach ($Candidate in $InnoCompilerCandidates) {
    if (Test-Path $Candidate) {
        $InnoCompiler = $Candidate
        break
    }
}

if ($null -eq $InnoCompiler) {
    Write-Host "Inno Setup was not found. Skipping installer build."
    Write-Host "Install Inno Setup, then run this script again."
}
else {
    Write-Host "Building installer with:"
    Write-Host $InnoCompiler

    & $InnoCompiler $InstallerScript

    Write-Host "Installer build finished."
}

Write-Host "=== Done ==="