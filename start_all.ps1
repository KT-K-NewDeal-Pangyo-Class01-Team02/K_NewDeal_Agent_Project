# ┌──────────────────────────────────────────────────────────────────────────┐
# │ 🔒 수정 금지: 이 파일은 관리자 이승현(EffortLEE1008)의 허락 없이 고치지 마세요.  │
# │    "창 하나로 모든 서버 실행 / 창을 닫으면 모두 종료" 방식은 바꾸지 않습니다.      │
# │    새 에이전트는 이 파일이 아니라 command_center/agents.json 의 "server" 로 추가.  │
# │    (루트 CLAUDE.md 의 "start_all 절대 규칙")                                    │
# └──────────────────────────────────────────────────────────────────────────┘
#
# Command Center 전체 실행
#   모든 에이전트 서버를 "이 창 하나"에서 띄우고 홈(http://localhost:5000)을 연다.
#   이 창을 닫거나 Ctrl+C 를 누르면 모든 서버가 함께 꺼진다.
#
#   사용법:  start_all.bat 더블클릭
#            또는 PowerShell 에서  .\start_all.ps1   (-DryRun: 계획만 보기, -NoBrowser: 브라우저 안 열기)
#
#   실행할 서버 목록은 command_center/agents.json 에서 읽는다. 이 스크립트는 고칠 필요가 없다.
#   새 에이전트를 붙이려면 agents.json 의 자기 항목에 "server" 를 적으면 된다 (command_center/README.md).
#       "server": { "dir": "내폴더", "port": 5005, "python": "패키지.app" }   ← python -m 패키지.app
#       "server": { "dir": "내폴더", "port": 5173, "npm": "dev" }             ← npm run dev
#
#   Python 위치를 자동으로 못 찾으면 이 폴더에 start_all.local.ps1 을 만들고 한 줄만 적는다 (git 에 안 올라감):
#       $Python = "C:\경로\python.exe"

param([switch]$DryRun, [switch]$NoBrowser)

$Root = $PSScriptRoot
$AgentsFile = Join-Path $Root "command_center\agents.json"
$LogDir = Join-Path $Root "logs"
$HubPort = 5000

# ── 실행할 서버: 허브(더 줘 Blueprint 포함) + agents.json 에서 "server" 가 있는 항목 ──
function Get-Servers {
    $list = @([pscustomobject]@{
        Name = "Command Center 홈 (+ 더 줘)"; Id = "command-center"; Dir = $Root; Port = $HubPort
        Python = "command_center.app"; Npm = $null
    })
    $agents = Get-Content $AgentsFile -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($a in $agents) {
        $s = $a.server
        if (-not $s) { continue }
        $list += [pscustomobject]@{
            Name = $a.name; Id = $a.id; Dir = (Join-Path $Root $s.dir); Port = [int]$s.port
            Python = $s.python; Npm = $s.npm
        }
    }
    return $list
}

# ── Python 찾기: start_all.local.ps1 → conda 환경들 → PATH. 필요한 패키지가 있는 것을 고른다 ──
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
    $candidates += Join-Path $Root ".venv\Scripts\python.exe"
    $candidates += Get-Command python -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notmatch "WindowsApps" } | ForEach-Object { $_.Source }
    $existing = $candidates | Where-Object { Test-Path $_ } | Select-Object -Unique
    # 1순위: 모든 에이전트 패키지가 있는 환경, 2순위: 허브(flask)만 되는 환경
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

# ── 다른 start_all 창이 이미 서버를 돌리고 있는지 (그 창의 서버는 건드리지 않는다) ──
#    ① 실행 중인 창이 남긴 표시 파일(logs\start_all.pid)의 프로세스가 살아 있거나
#    ② start_all.bat 처럼 'powershell -File …start_all.ps1' 로 떠 있는 창이 있으면 "다른 창이 실행 중"으로 본다.
$LockFile = Join-Path $LogDir "start_all.pid"
function Get-OtherStartAll {
    $found = @()
    if (Test-Path $LockFile) {
        $lockPid = 0
        if ([int]::TryParse((Get-Content $LockFile -Raw -ErrorAction SilentlyContinue).Trim(), [ref]$lockPid) -and $lockPid -ne $PID) {
            $p = Get-Process -Id $lockPid -ErrorAction SilentlyContinue
            if ($p -and $p.ProcessName -match '^(powershell|pwsh)$') { $found += $lockPid }
        }
    }
    $found += Get-CimInstance Win32_Process -Filter "Name='powershell.exe' OR Name='pwsh.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -match '-File\s+"?[^"]*start_all\.ps1' -and $_.CommandLine -notmatch '-DryRun' } |
        ForEach-Object { $_.ProcessId }
    return @($found | Select-Object -Unique)
}

# ── 이 프로젝트에서 띄웠다가 남은 서버 (창이 비정상 종료됐거나, 디버그 재시작 프로세스가 남은 경우) ──
#    우리 포트를 잡고 있는 프로세스 중, 그 서버의 'python -m <모듈>' 또는 그 서버 폴더의 node 인 것만 고른다.
#    디버그 모드는 부모·자식 2개로 뜨므로 같은 서버의 맨 위 프로세스까지 올라가서 반환한다(taskkill /T 로 통째로 끈다).
function Test-OurServer($proc, $s) {
    if (-not $proc) { return $false }
    $cmd = [string]$proc.CommandLine
    if ($s.Python) { return $proc.Name -match '^pythonw?\.exe$' -and $cmd -match ("\s-m\s+" + [regex]::Escape($s.Python) + "(\s|$)") }
    if ($s.Npm) { return $proc.Name -match '^(node|cmd)\.exe$' -and $cmd.IndexOf($s.Dir, [StringComparison]::OrdinalIgnoreCase) -ge 0 }
    return $false
}
function Get-LeftoverServers($servers) {
    $all = @{}
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object { $all[[int]$_.ProcessId] = $_ }
    $found = @()
    foreach ($s in $servers) {
        $owners = Get-NetTCPConnection -State Listen -LocalPort $s.Port -ErrorAction SilentlyContinue | ForEach-Object { [int]$_.OwningProcess }
        foreach ($o in ($owners | Select-Object -Unique)) {
            $cur = $all[$o]
            if (-not (Test-OurServer $cur $s)) { continue }
            while ($true) {
                $parent = $all[[int]$cur.ParentProcessId]
                if (-not (Test-OurServer $parent $s)) { break }
                $cur = $parent
            }
            $found += [pscustomobject]@{ Name = $s.Name; ProcessId = [int]$cur.ProcessId }
        }
    }
    return @($found | Sort-Object ProcessId -Unique)
}

# ── 안전장치: 이 창(스크립트)이 어떤 식으로 끝나든 여기서 띄운 모든 프로세스를 같이 끈다 ──
#    Windows "작업 개체(Job Object)" 에 KILL_ON_JOB_CLOSE 를 걸고 이 스크립트를 넣는다.
#    이후 띄우는 서버(와 그 자식 프로세스)는 자동으로 같은 작업에 들어간다.
function Enable-KillOnClose {
    if (-not ("CcJob" -as [type])) {
        Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class CcJob {
    [StructLayout(LayoutKind.Sequential)]
    struct BasicLimit {
        public long PerProcessUserTimeLimit; public long PerJobUserTimeLimit; public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize; public UIntPtr MaximumWorkingSetSize; public uint ActiveProcessLimit;
        public UIntPtr Affinity; public uint PriorityClass; public uint SchedulingClass;
    }
    [StructLayout(LayoutKind.Sequential)]
    struct IoCounters { public ulong R, W, O, RB, WB, OB; }
    [StructLayout(LayoutKind.Sequential)]
    struct ExtendedLimit {
        public BasicLimit Basic; public IoCounters Io; public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit; public UIntPtr PeakProcessMemoryUsed; public UIntPtr PeakJobMemoryUsed;
    }
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)] static extern IntPtr CreateJobObject(IntPtr attrs, string name);
    [DllImport("kernel32.dll")] static extern bool SetInformationJobObject(IntPtr job, int infoClass, ref ExtendedLimit info, uint size);
    [DllImport("kernel32.dll")] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
    static IntPtr job;  // 일부러 닫지 않는다: 이 프로세스가 끝나며 핸들이 닫히는 순간 작업 안의 프로세스가 모두 종료된다
    public static bool Enable() {
        job = CreateJobObject(IntPtr.Zero, null);
        if (job == IntPtr.Zero) return false;
        var info = new ExtendedLimit();
        info.Basic.LimitFlags = 0x2000;  // JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if (!SetInformationJobObject(job, 9, ref info, (uint)Marshal.SizeOf(typeof(ExtendedLimit)))) return false;
        return AssignProcessToJobObject(job, GetCurrentProcess());
    }
}
"@
    }
    return [CcJob]::Enable()
}

# ─────────────────────────────────────────────────────────────────────────────

$servers = Get-Servers
$python = $null
if ($servers | Where-Object { $_.Python }) {
    $python = Find-Python
    if ($python) { Write-Host "Python: $python" -ForegroundColor DarkGray }
    else { Write-Host "Python(flask 설치된 환경)을 찾지 못했어요. README.md 의 '처음 한 번만' 설정을 확인하거나 start_all.local.ps1 에 경로를 적어 주세요." -ForegroundColor Red }
}

if ($DryRun) {
    foreach ($s in $servers) {
        $cmd = if ($s.Python) { "$python -m $($s.Python)" } else { "npm run $($s.Npm)" }
        Write-Host "[DryRun] $($s.Name)  localhost:$($s.Port)"
        Write-Host "          폴더: $($s.Dir)"
        Write-Host "          명령: $cmd"
    }
    return
}

$Host.UI.RawUI.WindowTitle = "Command Center 서버 - 이 창을 닫으면 모두 종료"
if (-not (Enable-KillOnClose)) {
    Write-Warning "자동 종료 장치를 켜지 못했어요. 창을 닫아도 서버가 남아 있으면 작업 관리자에서 python 을 종료해 주세요."
}
New-Item -ItemType Directory -Force $LogDir | Out-Null
$env:PYTHONUNBUFFERED = "1"      # 로그가 바로바로 파일에 쓰이게
$env:PYTHONIOENCODING = "utf-8"  # 한글 로그 깨짐 방지

# ── 시작 전 정리 ──
$other = @(Get-OtherStartAll)
if ($other.Count -gt 0) {
    Write-Host "다른 start_all 창이 이미 서버를 실행 중이에요. 그 창을 그대로 쓰거나, 그 창을 닫은 뒤 다시 실행해 주세요." -ForegroundColor Yellow
    exit 1   # start_all.bat 이 창을 바로 닫지 않고 멈춰서 메시지를 보여 준다
}
if ($servers | Where-Object { Test-PortInUse $_.Port }) {
    $leftover = @(Get-LeftoverServers $servers)
    if ($leftover.Count -gt 0) {
        $names = ($leftover | ForEach-Object { $_.Name } | Select-Object -Unique) -join ", "
        Write-Host "이전에 실행하고 남은 서버를 정리합니다: $names" -ForegroundColor DarkGray
        foreach ($p in $leftover) { & taskkill.exe /PID $p.ProcessId /T /F 2>$null | Out-Null }
        $free = (Get-Date).AddSeconds(10)
        while ((Get-Date) -lt $free -and ($servers | Where-Object { Test-PortInUse $_.Port })) { Start-Sleep -Milliseconds 300 }
    }
}

Set-Content -Path $LockFile -Value $PID -Encoding ASCII

$running = @()
foreach ($s in $servers) {
    $label = "$($s.Name) (localhost:$($s.Port))"
    if (-not (Test-Path $s.Dir)) { Write-Host "[건너뜀] $label - 폴더 없음: $($s.Dir)" -ForegroundColor Yellow; continue }
    if (Test-PortInUse $s.Port) { Write-Host "[건너뜀] $label - 다른 프로그램이 이 포트를 쓰고 있어요 (이 창으로는 끌 수 없어요)" -ForegroundColor Yellow; continue }

    $out = Join-Path $LogDir "$($s.Id).log"
    $err = Join-Path $LogDir "$($s.Id).err.log"
    $start = @{ WorkingDirectory = $s.Dir; NoNewWindow = $true; PassThru = $true; RedirectStandardOutput = $out; RedirectStandardError = $err }
    if ($s.Python) {
        if (-not $python) { Write-Host "[건너뜀] $label - Python 없음" -ForegroundColor Yellow; continue }
        $proc = Start-Process -FilePath $python -ArgumentList @("-m", $s.Python) @start
    } elseif ($s.Npm) {
        if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Host "[건너뜀] $label - Node.js(npm) 가 설치되어 있지 않아요" -ForegroundColor Yellow; continue }
        $proc = Start-Process -FilePath "cmd.exe" -ArgumentList @("/c", "if not exist node_modules (npm install) && npm run $($s.Npm)") @start
    } else {
        Write-Host "[건너뜀] $label - agents.json 의 server 에 python 이나 npm 이 없어요" -ForegroundColor Yellow; continue
    }
    $running += [pscustomobject]@{ Name = $s.Name; Port = $s.Port; Label = $label; Process = $proc; Log = $out; Err = $err; Reported = $false }
    Write-Host "[시작]   $label" -ForegroundColor Green
}

if (-not $running) {
    Remove-Item $LockFile -ErrorAction SilentlyContinue
    Write-Host "`n새로 띄운 서버가 없어요." -ForegroundColor Yellow
    exit 1   # start_all.bat 이 창을 바로 닫지 않고 멈춰서 메시지를 보여 준다
}

# 서버가 포트를 열 때까지 기다린다 (최대 40초)
Write-Host "`n서버가 뜨기를 기다리는 중..." -ForegroundColor DarkGray
$deadline = (Get-Date).AddSeconds(40)
while ((Get-Date) -lt $deadline -and ($running | Where-Object { -not $_.Process.HasExited -and -not (Test-PortInUse $_.Port) })) {
    Start-Sleep -Milliseconds 500
}

Write-Host ""
foreach ($r in $running) {
    if (Test-PortInUse $r.Port) { Write-Host "  [OK]   $($r.Label)" -ForegroundColor Green }
    else { Write-Host "  [실패] $($r.Label)  → 로그: $($r.Err)" -ForegroundColor Red }
}

if (-not $NoBrowser -and (Test-PortInUse $HubPort)) {
    # explorer 를 거쳐 열어야 브라우저가 이 창과 함께 꺼지지 않는다
    Start-Process explorer.exe "http://localhost:$HubPort"
}

Write-Host "`n홈: http://localhost:$HubPort    로그 폴더: $LogDir" -ForegroundColor Cyan
Write-Host "이 창을 닫거나 Ctrl+C 를 누르면 모든 서버가 꺼집니다." -ForegroundColor Cyan

try {
    while ($true) {
        foreach ($r in $running) {
            if (-not $r.Reported -and $r.Process.HasExited) {
                $r.Reported = $true
                Write-Host "`n[멈춤] $($r.Label) 서버가 종료됐어요. 마지막 로그 ($($r.Err)):" -ForegroundColor Red
                if (Test-Path $r.Err) { Get-Content $r.Err -Tail 12 -Encoding UTF8 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray } }
            }
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Remove-Item $LockFile -ErrorAction SilentlyContinue
    Write-Host "`n서버를 끄는 중..." -ForegroundColor DarkGray
    foreach ($r in $running) {
        if (-not $r.Process.HasExited) { & taskkill.exe /PID $r.Process.Id /T /F 2>$null | Out-Null }
    }
}
