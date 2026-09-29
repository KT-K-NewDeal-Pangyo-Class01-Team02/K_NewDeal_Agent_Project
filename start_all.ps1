# Command Center 전체 실행: 모든 에이전트 서버를 각자 창으로 띄우고 홈(http://localhost:5000)을 연다.
#
#   사용법:  start_all.bat 더블클릭
#            또는 PowerShell 에서  .\start_all.ps1          (-DryRun 을 붙이면 실행하지 않고 계획만 보여 줌)
#
#   서버 목록은 아래 $Servers 에 있습니다. 각자 자기 에이전트 줄만 추가·수정하세요 (루트 CLAUDE.md 규칙).
#   Python 위치를 자동으로 못 찾으면, 이 폴더에 start_all.local.ps1 을 만들고 한 줄만 적으세요 (git 에 안 올라감):
#       $Python = "C:\경로\python.exe"

param([switch]$DryRun)

$Root = $PSScriptRoot

# ── 서버 목록 (포트 표는 README.md / CLAUDE.md) ─────────────────────────────
$Servers = @(
    @{ Name = "Command Center 홈"; Port = 5000; Dir = "";                       Kind = "python"; Module = "command_center.app" }
    @{ Name = "통하길 스튜디오";   Port = 5004; Dir = "tonghagil_LEESEUNGHYUN"; Kind = "python"; Module = "tonghagil_studio.app" }
    @{ Name = "더 줘";             Port = 5173; Dir = "thejo_project";          Kind = "npm";    Script = "dev" }
    # 최우용 (vicDDory_wooyong): 실행 방법과 포트가 정해지면 여기에 한 줄 추가
)

# ── Python 찾기: start_all.local.ps1 → conda 환경들 → PATH 순서. flask 가 설치된 것을 고른다 ──
function Find-Python {
    $local = Join-Path $Root "start_all.local.ps1"
    if (Test-Path $local) {
        . $local
        if ($Python -and (Test-Path $Python)) { return $Python }
        Write-Warning "start_all.local.ps1 의 `$Python 경로가 없습니다: $Python"
    }
    $candidates = @()
    foreach ($base in @("$env:USERPROFILE\anaconda3", "$env:USERPROFILE\miniconda3", "C:\ProgramData\anaconda3", "C:\ProgramData\miniconda3", "$env:LOCALAPPDATA\anaconda3")) {
        if (Test-Path "$base\envs") {
            $candidates += Get-ChildItem "$base\envs" -Directory | ForEach-Object { Join-Path $_.FullName "python.exe" }
        }
        $candidates += Join-Path $base "python.exe"
    }
    $candidates += Get-Command python -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notmatch "WindowsApps" } | ForEach-Object { $_.Source }
    $existing = $candidates | Where-Object { Test-Path $_ } | Select-Object -Unique
    # 1순위: 허브 + 통하길 스튜디오 패키지가 모두 있는 환경, 2순위: 허브(flask)만 되는 환경
    foreach ($imports in @("import flask, dotenv, requests, google.auth", "import flask, dotenv")) {
        foreach ($py in $existing) {
            & $py -c $imports 2>$null
            if ($LASTEXITCODE -eq 0) { return $py }
        }
    }
    return $null
}

function Test-PortInUse($port) {
    return [bool](Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
}

$python = $null
if ($Servers | Where-Object { $_.Kind -eq "python" }) {
    $python = Find-Python
    if (-not $python) {
        Write-Host "Python(flask 설치된 환경)을 찾지 못했어요. README.md 의 '처음 한 번만' 설정을 확인하거나 start_all.local.ps1 에 경로를 적어 주세요." -ForegroundColor Red
    } else {
        Write-Host "Python: $python" -ForegroundColor DarkGray
    }
}

foreach ($s in $Servers) {
    $dir = if ($s.Dir) { Join-Path $Root $s.Dir } else { $Root }
    $label = "$($s.Name) (localhost:$($s.Port))"

    if (-not (Test-Path $dir)) { Write-Host "건너뜀  $label - 폴더 없음: $dir" -ForegroundColor Yellow; continue }
    if (Test-PortInUse $s.Port) { Write-Host "건너뜀  $label - 이미 실행 중" -ForegroundColor Yellow; continue }

    if ($s.Kind -eq "python") {
        if (-not $python) { Write-Host "건너뜀  $label - Python 없음" -ForegroundColor Yellow; continue }
        $command = "& '$python' -m $($s.Module)"
    } elseif ($s.Kind -eq "npm") {
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Host "건너뜀  $label - Node.js(npm) 가 설치되어 있지 않아요" -ForegroundColor Yellow; continue }
        # 처음이면 npm install 부터
        $command = "if (-not (Test-Path node_modules)) { npm install }; npm run $($s.Script)"
    } else {
        Write-Host "건너뜀  $label - 알 수 없는 Kind: $($s.Kind)" -ForegroundColor Yellow; continue
    }

    $windowCommand = "`$Host.UI.RawUI.WindowTitle = '$($s.Name) :$($s.Port)'; Write-Host '$label  (이 창을 닫으면 서버가 꺼집니다)' -ForegroundColor Cyan; $command"
    if ($DryRun) {
        Write-Host "[DryRun] $label"
        Write-Host "          폴더: $dir"
        Write-Host "          명령: $command"
    } else {
        Start-Process powershell -WorkingDirectory $dir -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-Command", $windowCommand)
        Write-Host "실행    $label" -ForegroundColor Green
    }
}

if (-not $DryRun) {
    Start-Sleep -Seconds 4
    Start-Process "http://localhost:5000"
    Write-Host "`n브라우저에서 http://localhost:5000 을 열었어요. 서버를 끄려면 각 서버 창을 닫으세요." -ForegroundColor Cyan
}
