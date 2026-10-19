[CmdletBinding()]
param(
    [string]$VaultPath,
    [string]$CodexHome,
    [switch]$EnableRemoteSync,
    [switch]$Uninstall
)

$ErrorActionPreference = 'Stop'
$taskName = 'Codex Obsidian Export'
$installRoot = Join-Path $env:LOCALAPPDATA 'CodexObsidianExport'
$configPath = Join-Path $installRoot 'config.json'
$receiptPath = Join-Path $installRoot 'installation.json'
$exporterPath = Join-Path $installRoot 'export_codex_chats.py'
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Codex Obsidian Export.lnk'
$owner = 'codex-obsidian-export-v1'
$existing = $null
$taskCreatedHere = $false
if (Test-Path -LiteralPath $configPath) {
    $existing = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
    if ($existing.owner -ne $owner) { throw 'Installation directory contains unrelated configuration; left unchanged.' }
}

function Write-LocalJson([string]$Path, $Value) {
    [System.IO.File]::WriteAllText($Path, ($Value | ConvertTo-Json -Depth 8) + "`n", [System.Text.UTF8Encoding]::new($false))
}

function Get-OwnedWatcher {
    if (-not (Test-Path -LiteralPath $receiptPath)) { return $null }
    $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json
    if ($receipt.owner -ne $owner) { return $null }
    if (-not $receipt.watcher_pid) { return $null }
    $candidate = Get-CimInstance Win32_Process -Filter "ProcessId=$($receipt.watcher_pid)" -ErrorAction SilentlyContinue
    if ($candidate -and $candidate.CommandLine -and $candidate.CommandLine.Contains($exporterPath) -and $candidate.CommandLine.Contains($configPath) -and $candidate.CommandLine.Contains('--watch')) {
        return $candidate
    }
    return $null
}

function Get-OwnedTask {
    $candidateTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (-not $candidateTask) { return $null }
    if (-not $existing -and -not $taskCreatedHere) { throw 'An unrelated scheduled task uses this name; left unchanged.' }
    $ownedAction = @($candidateTask.Actions | Where-Object {
        $_.Arguments -and $_.Arguments.Contains('"' + $exporterPath + '"') -and $_.Arguments.Contains('"' + $configPath + '"')
    })
    if ($ownedAction.Count -ne 1 -or @($candidateTask.Actions).Count -ne 1) {
        throw 'Scheduled task actions do not match this exporter; left unchanged.'
    }
    return $candidateTask
}

function Get-OwnedStartup {
    if (-not (Test-Path -LiteralPath $shortcutPath)) { return $null }
    $link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
    if (-not $existing -or -not $link.Arguments.Contains('"' + $exporterPath + '"') -or -not $link.Arguments.Contains('"' + $configPath + '"')) {
        throw 'Startup shortcut does not match this exporter; left unchanged.'
    }
    return $link
}

function Remove-OwnedStartup {
    if (Get-OwnedStartup) { Remove-Item -LiteralPath $shortcutPath }
}

if ($Uninstall) {
    if (-not $existing) { throw 'No owned installation found.' }
    $existing.enabled = $false
    Write-LocalJson $configPath $existing
    $watcher = Get-OwnedWatcher
    if ($watcher) { Stop-Process -Id $watcher.ProcessId }
    if (Get-OwnedTask) {
        Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    }
    Remove-OwnedStartup
    Write-Output 'Automatic export disabled. Installed files and all Obsidian notes were preserved.'
    return
}

if (-not $VaultPath) {
    if ($existing) {
        $VaultPath = $existing.vault
    } else {
        $registryPath = Join-Path $env:APPDATA 'obsidian\obsidian.json'
        if (-not (Test-Path -LiteralPath $registryPath)) { throw 'Specify -VaultPath for an existing Obsidian vault.' }
        $registry = Get-Content -Raw -LiteralPath $registryPath | ConvertFrom-Json
        $vaults = @($registry.vaults.PSObject.Properties.Value)
        $openVaults = @($vaults | Where-Object open -EQ $true)
        if ($openVaults.Count -eq 1) { $VaultPath = $openVaults[0].path }
        elseif ($vaults.Count -eq 1) { $VaultPath = $vaults[0].path }
        else { throw 'Multiple vaults found; specify -VaultPath.' }
    }
}
$vault = (Get-Item -LiteralPath $VaultPath).FullName
if (-not (Test-Path -LiteralPath $vault -PathType Container)) { throw 'Vault path must be an existing directory.' }
if (-not $CodexHome) {
    if ($env:CODEX_HOME) { $CodexHome = $env:CODEX_HOME }
    else { $CodexHome = Join-Path ([Environment]::GetFolderPath('UserProfile')) '.codex' }
}
$CodexHome = (Get-Item -LiteralPath $CodexHome).FullName
$task = Get-OwnedTask
if ($task -and -not $existing) { throw 'An unrelated task already uses this name; left unchanged.' }
if ((Test-Path -LiteralPath $shortcutPath) -and -not $existing) { throw 'An unrelated startup shortcut already uses this name.' }
Get-OwnedStartup | Out-Null

$pythonCommand = Get-Command python -ErrorAction Stop
$python = (& $pythonCommand.Source -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
& $python -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
$pythonw = Join-Path (Split-Path $python) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { throw 'pythonw.exe is required for invisible background execution.' }

New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'export_codex_chats.py') -Destination $exporterPath
$config = [ordered]@{
    owner = $owner
    enabled = $true
    vault = $vault
    folder = 'AI Conversations/Codex'
    codex_home = $CodexHome
    emdash_databases = @((Join-Path $env:APPDATA 'emdash\conversations.db'), (Join-Path $env:APPDATA 'emdash\emdash4.db'))
    state_dir = (Join-Path $installRoot 'state')
    remotely_save_sync = ($EnableRemoteSync.IsPresent -or ($existing -and $existing.remotely_save_sync -eq $true))
}
Write-LocalJson $configPath $config
& $python $exporterPath --config $configPath
if ($LASTEXITCODE -ne 0) { throw 'Initial export failed. Automation was not enabled; source chats are unchanged.' }

$mode = 'scheduled-task'
$watcherPid = $null
try {
    $arguments = '"' + $exporterPath + '" --config "' + $configPath + '"'
    $action = New-ScheduledTaskAction -Execute $pythonw -Argument $arguments -WorkingDirectory $installRoot
    $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $triggers = @(
        (New-ScheduledTaskTrigger -AtLogOn -User $user),
        (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1))
    )
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Archive local Codex/Emdash chats; optionally request the connected Obsidian plugin to sync. No inference.' -Force | Out-Null
    $taskCreatedHere = $true
    Start-ScheduledTask -TaskName $taskName
} catch {
    # Do not leave an enabled scheduled task alongside the fallback watcher.
    if (Get-OwnedTask) { Disable-ScheduledTask -TaskName $taskName -ErrorAction Stop | Out-Null }
    # Per-user Startup needs no administrator/Scheduler rights. The same exporter handles both modes.
    $mode = 'startup-watcher'
    Get-OwnedStartup | Out-Null
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $pythonw
    $shortcut.Arguments = '"' + $exporterPath + '" --config "' + $configPath + '" --watch'
    $shortcut.WorkingDirectory = $installRoot
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Automatically archive local Codex conversations in Obsidian'
    $shortcut.Save()
    $watcher = Get-OwnedWatcher
    # Restart only our verified watcher so it loads the refreshed exporter.
    if ($watcher) { Stop-Process -Id $watcher.ProcessId }
    $process = Start-Process -FilePath $pythonw -ArgumentList $shortcut.Arguments -WorkingDirectory $installRoot -WindowStyle Hidden -PassThru
    $watcherPid = $process.Id
}
if ($mode -eq 'scheduled-task') {
    $watcher = Get-OwnedWatcher
    if ($watcher) { Stop-Process -Id $watcher.ProcessId }
    Remove-OwnedStartup
}
Write-LocalJson $receiptPath ([ordered]@{ owner=$owner; mode=$mode; watcher_pid=$watcherPid; task_name=$taskName })
Write-Output "Automatic export installed ($mode). Notes: $vault\AI Conversations\Codex\Index.md"
