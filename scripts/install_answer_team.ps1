[CmdletBinding()]
param([switch]$EnableTelemetry)
$ErrorActionPreference = 'Stop'
$installRoot = Join-Path $env:LOCALAPPDATA 'EmdashAnswerTeam'
$projectRoot = Split-Path $PSScriptRoot
$python = (& python -c 'import sys; print(sys.executable)').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
$codex = Get-Command codex.cmd -ErrorAction Stop
$needsRegistration = $true
$existingText = & $codex.Source mcp list --json 2>$null
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect existing MCP registrations; no settings changed.' }
$existing = @(($existingText -join "`n") | ConvertFrom-Json) | Where-Object { $_.name -eq 'answer_team' }
if ($existing) {
    # Preserve unrelated same-name servers rather than replacing them.
    $existingArguments = @($existing.transport.args) + @($existing.args)
    if (-not ($existingArguments -contains (Join-Path $installRoot 'answer_team.py'))) {
        throw 'An unrelated answer_team MCP server already exists; left unchanged.'
    }
    $needsRegistration = -not (($existingArguments -contains $projectRoot) -and ($existing.transport.command -eq $python))
}
New-Item -ItemType Directory -Path $installRoot -Force | Out-Null
foreach ($name in @('answer_team.py', 'answer_telemetry.py', 'validate_repo.py', 'check_models.py', 'check_provider_access.py', 'model_routing.py')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $name) -Destination (Join-Path $installRoot $name)
}
if ($needsRegistration) {
    & $codex.Source mcp add answer_team -- $python (Join-Path $installRoot 'answer_team.py') --project-root $projectRoot --mcp
    if ($LASTEXITCODE -ne 0) { throw 'MCP registration failed.' }
}
# Codex's default tool timeout is too short for three sequential cloud stages.
# Update only this owned server's scalar fields; preserve unrelated user configuration.
$configRoot = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }
$configPath = Join-Path $configRoot 'config.toml'
@'
import re
import json
import sys
import tomllib
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
tomllib.loads(text)
lines = text.splitlines(keepends=True)
start = next((i for i, line in enumerate(lines) if line.strip() == "[mcp_servers.answer_team]"), None)
if start is None:
    raise SystemExit("Cannot locate owned MCP section; configuration left unchanged.")
end = next((i for i in range(start + 1, len(lines)) if lines[i].lstrip().startswith("[")), len(lines))
section = "".join(lines[start + 1:end])
for key, value in (("startup_timeout_sec", "15"), ("tool_timeout_sec", "300"), ("enabled_tools", '["ask_team"]')):
    pattern = rf"(?m)^{key}\s*=.*$"
    replacement = f"{key} = {value}"
    if re.search(pattern, section):
        section = re.sub(pattern, replacement, section)
    else:
        section = section.rstrip() + "\n" + replacement + "\n"
updated = "".join(lines[:start + 1]) + section.rstrip() + "\n\n" + "".join(lines[end:])
parsed = tomllib.loads(updated)
if sys.argv[2] == "1":
    env = dict(parsed["mcp_servers"]["answer_team"].get("env", {}))
    env["ANSWER_TEAM_LANGFUSE"] = "1"
    header = "[mcp_servers.answer_team.env]"
    updated_lines = updated.splitlines(keepends=True)
    env_start = next((i for i, line in enumerate(updated_lines) if line.strip() == header), None)
    if env_start is not None:
        env_end = next((i for i in range(env_start + 1, len(updated_lines)) if updated_lines[i].lstrip().startswith("[")), len(updated_lines))
        contents = "".join(updated_lines[env_start + 1:env_end])
        pattern = r'(?m)^ANSWER_TEAM_LANGFUSE\s*=.*$'
        contents = re.sub(pattern, 'ANSWER_TEAM_LANGFUSE = "1"', contents) if re.search(pattern, contents) else contents.rstrip() + '\nANSWER_TEAM_LANGFUSE = "1"\n'
        updated = "".join(updated_lines[:env_start + 1]) + contents.rstrip() + "\n\n" + "".join(updated_lines[env_end:])
    elif re.search(r'(?m)^env\s*=', section):
        replacement = "env = { " + ", ".join(json.dumps(k) + " = " + json.dumps(v) for k, v in env.items()) + " }"
        section = re.sub(r'(?m)^env\s*=.*$', lambda match: replacement, section)
        updated = "".join(lines[:start + 1]) + section.rstrip() + "\n\n" + "".join(lines[end:])
    else:
        updated = updated.rstrip() + '\n\n' + header + '\nANSWER_TEAM_LANGFUSE = "1"\n'
    tomllib.loads(updated)
if updated != text:
    path.write_text(updated, encoding="utf-8")
'@ | & $python - $configPath ([int]$EnableTelemetry.IsPresent)
if ($LASTEXITCODE -ne 0) { throw 'MCP timeout configuration failed.' }
Write-Output 'Read-only answer_team MCP server registered for this project. Reload/restart the Codex conversation to discover the tool.'
