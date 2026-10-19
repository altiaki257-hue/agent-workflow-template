# Local Codex conversation archive

The exporter saves local Codex conversations, including Codex sessions started through Emdash, as Markdown notes in an existing Obsidian vault. By default it makes no network or model requests. An explicit opt-in can request cloud sync through the already-configured Remotely Save plugin. It does not modify Codex/Emdash source data or authentication.

## Windows installation

From the repository in PowerShell:

```powershell
.\scripts\install_chat_export.ps1
```

The installer discovers the single open vault from Obsidian's registry. With multiple vaults, explicitly supply `-VaultPath` for the desired existing directory. Python 3.11+ and `pythonw.exe` are required.

The installer copies a standalone exporter to `%LOCALAPPDATA%\CodexObsidianExport`, stores machine paths in local `config.json`, and registers the per-user **Codex Obsidian Export** task. It runs at login and every minute while signed in, using `pythonw.exe` without a console. It does not rely on keeping this worktree or Obsidian open. Rerun the installer after updating the exporter code.

If Windows does not permit task registration, the installer uses a per-user Startup shortcut and a hidden one-minute watcher instead. It validates ownership before changing an existing named task/shortcut, stops only its verified watcher when switching to a task, and disables its task before enabling the fallback. It does not request administrator privileges or alter existing Codex hooks/configuration.

## Optional Remotely Save automation

Install and connect Remotely Save in the archive vault first, then run the installer with `-EnableRemoteSync`. This persists `remotely_save_sync: true` in the local exporter configuration; subsequent installs preserve the opt-in. Set that field to `false` to disable export-triggered requests.

After each batch that changes notes or the index, the exporter uses the Obsidian CLI to verify the open vault path and request the fixed `remotely-save:start-sync` command. Credentials stay in the plugin. No command comes from conversation content. Each CLI call has a ten-second timeout and hidden output. Failed requests cannot fail the export: `remote_sync: deferred` is recorded and retried on the next export check, even without new changes. `requested` means the CLI acknowledged the command, not that cloud delivery succeeded.

Obsidian must be running with this vault open and its CLI enabled. The exporter does not launch it. In Remotely Save, periodic sync every minute and startup sync after ten seconds provide catch-up after Obsidian reopens and after failed cloud transfers. Sync on save can also be enabled, but version 0.5.25 checks the active note, so it is insufficient for background log updates on its own. Plugin timers run only while Obsidian is open; configure the phone separately to use the same provider, remote folder and encryption settings. This syncs according to the vault's existing inclusion/exclusion settings, not just the newly exported log.

The local owner setup uses OneDrive and remote folder `Emdash Logs`. No credential values are stored in repository task records. First-sync and remote delivery results belong in the task handoff.

## Notes and update behavior

Open `AI Conversations/Codex/Index.md` in the vault. Each session has one stable `<session-id>.md` note with its title, working directory, branch, timestamps, parent-session reference, and user/assistant text. Emdash labels come from read-only conversation metadata when available. Sessions and archived sessions under the configured Codex home are included; forked agents retain their own thread identity despite embedded parent history.

The exporter merges mixed transcript formats, deduplicating positively matched message IDs or nearby identical timestamped copies. Ambiguous repeated text is preserved, so occasional duplicates are preferable to losing real messages. Active transcripts take precedence over archived duplicates. Per-session label fingerprints avoid reparsing unrelated sessions after a title change. Unchanged sources are skipped; incomplete JSONL is retried. Files are replaced atomically. Add annotations in **Personal notes**, outside the generated markers: that content survives updates. Editing/removing generated markers preserves the existing note and reports an error. Source deletion never deletes archived notes.

Only recognized user/assistant text is included. System/developer roles, recognized injected instruction prefixes in every supported format, internal reasoning, tool arguments/output, and attachment bytes are omitted. Common provider tokens, GitHub/AWS credentials, bearer tokens, and private-key blocks are redacted on a best-effort basis. This is a personal archive, not a complete secret/instruction-removal guarantee; the vault's normal sync settings still apply.

## Check or export immediately

```powershell
$archiveInstall = Join-Path $env:LOCALAPPDATA 'CodexObsidianExport'
python (Join-Path $archiveInstall 'export_codex_chats.py') --config (Join-Path $archiveInstall 'config.json')
Get-ScheduledTaskInfo -TaskName 'Codex Obsidian Export'
Get-Content (Join-Path $archiveInstall 'state\status.json')
```

Status contains counts and timestamps, never chat contents. `errors`, `unsupported_emdash`, `metadata_unavailable`, and `emdash_without_local_transcript` surface incomplete coverage. The index also lists unavailable/non-Codex Emdash coverage. The manifest, lock and status files remain outside Git. There is no paid inference and no external Python dependency.

For a manual one-off in the native Codex terminal, `/export session.md` is the [documented Markdown export command](https://learn.chatgpt.com/docs/developer-commands). This automation produces Markdown independently; it does not inject slash commands into Emdash or the terminal.

## Disable

```powershell
.\scripts\install_chat_export.ps1 -Uninstall
```

This disables automatic execution and removes its task/Startup shortcut while preserving installed files and every Obsidian note. The uninstall flag is an explicit operation; normal install/export never removes conversations.

## Compatibility and limits

The adapter was verified against local Codex 0.163.0 transcript shapes and Emdash's `conversation_records`/legacy `conversations` metadata tables. The [official hook documentation](https://learn.chatgpt.com/docs/hooks) states that transcript format is not stable; unsupported formats produce an error count, not a silently fabricated transcript. Fixture tests cover the recognized variants.

Remote-only conversations without a local transcript cannot be recovered by this local exporter. Emdash conversations using other providers need their own adapters and are explicitly counted as unsupported. Future alternative `CODEX_HOME` locations require updating the local configuration or rerunning the installer with `-CodexHome`. No cloud ChatGPT browser history is accessed.
