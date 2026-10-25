"""Archive local chats; optionally request cloud sync through the Obsidian CLI."""

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unicodedata
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

OWNER = "codex-obsidian-export-v1"
FORMAT_VERSION = 4
FILENAME_VERSION = 1
SESSION_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{35}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|(?:AKIA|ASIA)[A-Z0-9]{16})\b"
)
PRIVATE_KEY = re.compile(
    r"-----BEGIN ([A-Z ]*PRIVATE KEY)-----.*?-----END \1-----", re.DOTALL
)
BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]{12,}=*")


class ArchiveError(Exception):
    """An error that can be reported without disclosing conversation content."""


@dataclass
class Conversation:
    session_id: str
    created: str
    cwd: str
    branch: str
    parent: str
    messages: list
    malformed: int = 0
    agent: str = ""


class ExportState(TypedDict):
    files: dict[str, dict]
    remote_sync_pending: NotRequired[bool]


class ExportCounts(TypedDict):
    updated: int
    unchanged: int
    errors: int
    renamed: int
    unsupported_emdash: int
    metadata_unavailable: int
    partial_transcripts: int
    emdash_without_local_transcript: NotRequired[int]
    notes: NotRequired[int]
    remote_sync: NotRequired[Literal["deferred", "requested", "unchanged"]]


def redact(text):
    text = PRIVATE_KEY.sub("[REDACTED PRIVATE KEY]", text)
    text = TOKEN.sub("[REDACTED TOKEN]", text)
    return BEARER.sub("Bearer [REDACTED]", text)


def extract_text(content):
    if isinstance(content, str):
        return content
    parts = []
    for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
            continue
        kind = str(block.get("type", "")).lower()
        if kind in {"text", "input_text", "output_text"} and isinstance(
            block.get("text"), str
        ):
            parts.append(block["text"])
        elif kind in {"image", "input_image", "localimage", "local_image"}:
            parts.append("[Image attachment omitted]")
    return "\n\n".join(parts)


def parse_transcript(path):
    """Prefer completed UI messages; support older event/response transcript formats."""
    meta = {}
    native, legacy, responses = [], [], []
    malformed = 0
    with path.open(encoding="utf-8", errors="replace") as stream:
        for ordinal, line in enumerate(stream):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                malformed += 1  # A live writer can leave an incomplete final line.
                continue
            if not isinstance(row, dict) or not isinstance(row.get("payload"), dict):
                continue
            payload = row["payload"]
            kind = row.get("type")
            stamp = row.get("timestamp", "")
            if kind == "session_meta":
                # Forked agents embed parent history, including a second parent session_meta.
                # The first record identifies this file's thread; later parent records must not replace it.
                if not meta or payload.get("id") == meta.get("id"):
                    meta.update(payload)
            elif kind == "event_msg":
                if payload.get("type") == "item_completed":
                    item = payload.get("item", {})
                    if not isinstance(item, dict):
                        continue
                    role = {"UserMessage": "user", "AgentMessage": "assistant"}.get(
                        str(item.get("type", ""))
                    )
                    if role:
                        native.append(
                            (
                                item.get("id"),
                                role,
                                extract_text(item.get("content")),
                                stamp,
                                ordinal,
                                3,
                            )
                        )
                elif payload.get("type") in {"user_message", "agent_message"}:
                    role = "user" if payload["type"] == "user_message" else "assistant"
                    legacy.append(
                        (
                            None,
                            role,
                            extract_text(payload.get("message", "")),
                            stamp,
                            ordinal,
                            2,
                        )
                    )
            elif kind == "response_item" and payload.get("type") == "message":
                role = payload.get("role")
                if role in {"user", "assistant"}:
                    body = extract_text(payload.get("content"))
                    if body.lstrip().startswith(
                        (
                            "<environment_context>",
                            "# AGENTS.md instructions",
                            "<INSTRUCTIONS>",
                        )
                    ):
                        continue
                    responses.append((payload.get("id"), role, body, stamp, ordinal, 1))
    session_id = meta.get("id") or meta.get("session_id")
    if not isinstance(session_id, str) or not SESSION_ID.fullmatch(session_id):
        raise ArchiveError("transcript has no supported session identity")
    # Prefer richer completed events only for positively matched duplicates, not the whole file.
    # Keep unmatched older formats and repeated genuine messages, even if a client upgraded mid-chat.
    messages, seen, equivalents = [], set(), {}
    for message_id, role, body, stamp, ordinal, priority in sorted(
        native + legacy + responses, key=lambda row: (-row[5], row[4])
    ):
        if not body or body.lstrip().startswith(
            ("<environment_context>", "# AGENTS.md instructions", "<INSTRUCTIONS>")
        ):
            continue
        if message_id:
            if (role, message_id) in seen:
                continue
            seen.add((role, message_id))
        duplicate = False
        for previous_ordinal in range(ordinal - 3, ordinal + 4):
            previous = equivalents.get((role, body, previous_ordinal))
            if previous is None:
                continue
            previous_stamp, previous_priority = previous
            if previous_priority <= priority:
                continue
            if stamp and previous_stamp and stamp == previous_stamp:
                duplicate = True
                break
        if duplicate:
            continue
        equivalents[(role, body, ordinal)] = (stamp, priority)
        messages.append((ordinal, role, body, stamp))
    messages = [(role, body, stamp) for _, role, body, stamp in sorted(messages)]
    if not messages:
        raise ArchiveError(
            "no supported user/assistant messages; source format may have changed"
        )
    git = meta.get("git")
    if not isinstance(git, dict):
        git = {}
    return Conversation(
        session_id,
        str(meta.get("timestamp", "")),
        str(meta.get("cwd", "")),
        str(git.get("branch", "")),
        str(meta.get("parent_thread_id") or meta.get("forked_from_id") or ""),
        messages,
        malformed,
        str(meta.get("agent_nickname", "")),
    )


def emdash_metadata(databases):
    """Read only conversation labels/links. Never read config, credentials or app_secrets."""
    result, unsupported, unavailable = {}, set(), 0
    for path in databases:
        path = Path(path)
        if not path.is_file():
            continue
        try:
            with closing(
                sqlite3.connect(
                    path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2
                )
            ) as db:
                db.execute("PRAGMA query_only=ON")
                tables = {
                    row[0]
                    for row in db.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
                if "conversation_records" in tables:
                    rows = db.execute(
                        "SELECT id,provider,title,cwd,provider_link FROM conversation_records"
                    )
                    for record_id, provider, title, cwd, link in rows:
                        if provider != "codex":
                            unsupported.add((provider, record_id))
                            continue
                        try:
                            session_id = json.loads(link).get("providerSessionId")
                        except (ValueError, AttributeError, TypeError):
                            continue
                        if session_id:
                            result[session_id] = {
                                "title": title,
                                "cwd": cwd,
                                "client": "Emdash",
                            }
                elif "conversations" in tables:
                    rows = db.execute(
                        "SELECT id,provider,title,cwd,provider_session_id FROM conversations"
                    )
                    for record_id, provider, title, cwd, session_id in rows:
                        if provider != "codex":
                            unsupported.add((provider, record_id))
                        elif session_id:
                            result.setdefault(
                                session_id,
                                {"title": title, "cwd": cwd, "client": "Emdash"},
                            )
        except sqlite3.Error:
            unavailable += 1
    return result, len(unsupported), unavailable


def safe_path(root, relative):
    """Keep generated files under their configured root; refuse existing symlink components."""
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ArchiveError("unsafe destination path")
    root = root.absolute()
    target = root / relative
    for part in (root, *root.parents, target, *target.parents):
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ArchiveError("symlink/junction destination is not supported")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ArchiveError("destination escaped its root")
    return target


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=".codex-export-",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def managed_write(path, identity, generated):
    """Replace only a unique owned section. Everything outside it is preserved."""
    begin = f"<!-- {OWNER}:begin {identity} -->"
    end = f"<!-- {OWNER}:end {identity} -->"
    generated = generated.replace(f"<!-- {OWNER}", f"&lt;!-- {OWNER}")
    section = begin + "\n" + generated.rstrip() + "\n" + end
    if path.exists():
        old = path.read_text(encoding="utf-8")
        if (
            old.count(begin) != 1
            or old.count(end) != 1
            or old.index(end) < old.index(begin)
        ):
            raise ArchiveError(
                "existing note has missing/ambiguous ownership markers; left unchanged"
            )
        new = old[: old.index(begin)] + section + old[old.index(end) + len(end) :]
        if new == old:
            return False
    else:
        new = section + "\n\n## Personal notes\n\n"
    atomic_write(path, new)
    return True


def created_time(value):
    """Normalize timestamps for deterministic chronological names across machines."""
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None


def readable_filename(created, title, session_id):
    stamp = created_time(created)
    prefix = stamp.strftime("%Y-%m-%d %H-%M-%S UTC") if stamp else "Undated"
    title = re.sub(r"https?://\S+", "link", redact(str(title)))
    title = "".join(" " if unicodedata.category(c).startswith("C") else c for c in title)
    title = re.sub(r'[<>:"/\\|?*\[\]#^]', " ", title)
    title = " ".join(title.split())[:64].rstrip(" .-_") or "Conversation"
    while len(title.encode("utf-8")) > 128:
        title = title[:-1].rstrip(" .-_")
    identity = hashlib.sha256(session_id.encode()).hexdigest()[:8]
    return f"{prefix} - {title} - {identity}.md"


def owned_note_text(path, session_id):
    text = path.read_text(encoding="utf-8")
    begin = f"<!-- {OWNER}:begin {session_id} -->"
    end = f"<!-- {OWNER}:end {session_id} -->"
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(end) < text.index(begin):
        raise ArchiveError("note ownership markers are invalid; left unchanged")
    return text


def name_note(archive, entry, session_id, title, created, rename_note=None):
    """Move an owned legacy note without replacing any existing destination."""
    filename = (
        entry["file"]
        if entry.get("filename_version") == FILENAME_VERSION
        else readable_filename(created, title, session_id)
    )
    old = safe_path(archive, entry.get("file", session_id + ".md"))
    new = safe_path(archive, filename)
    renamed = False
    if old != new and old.exists():
        owned_note_text(old, session_id)
        if new.exists():
            raise ArchiveError("rename destination already exists; both notes preserved")
        if rename_note is not None:
            rename_note(old, new)
            if old.exists() or not new.is_file():
                raise ArchiveError("note rename did not complete")
        else:
            # Publish without replacement, then remove only the original directory entry.
            os.link(old, new)
            old.unlink()
        renamed = True
    return filename, renamed


def render(conversation, label):
    first_question = next(
        (body for role, body, _ in conversation.messages if role == "user" and body.strip()),
        "",
    )
    fallback = next((line.strip() for line in first_question.splitlines() if line.strip()), "")
    title = label.get("title") or fallback[:100] or conversation.agent or "Codex conversation"
    title = redact(" ".join(str(title).split()))
    fields = {
        "session_id": conversation.session_id,
        "client": label.get("client", "Codex"),
        "created": conversation.created,
        "working_directory": label.get("cwd") or conversation.cwd,
        "branch": conversation.branch,
        "parent_session": conversation.parent,
    }
    lines = [
        "# " + title,
        "",
        "Automatic local archive. Add annotations outside the generated section.",
        "",
    ]
    for key, value in fields.items():
        if value:
            lines.append(
                f"- **{key.replace('_', ' ').title()}:** "
                + redact(str(value).replace("\n", " "))
            )
    lines.extend(
        [
            "",
            "Internal instructions, reasoning, tool payloads, and binary attachments are omitted.",
            "",
        ]
    )
    for role, body, stamp in conversation.messages:
        lines.extend(
            [
                f"## {role.title()}" + (f" · {stamp}" if stamp else ""),
                "",
                redact(body),
                "",
            ]
        )
    return "\n".join(lines), title


@contextmanager
def run_lock(path):
    """OS releases this lock even if an exporter crashes; no stale PID deletion."""
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = path.open("a+b")
    locked = False
    try:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        yield
    finally:
        if locked:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def request_remote_sync(vault):
    """Request a fixed plugin command without exposing CLI output or starting Obsidian."""
    cli = shutil.which("obsidian")
    if not cli:
        return "deferred"
    options = {
        "capture_output": True,
        "text": True,
        "timeout": 10,
        "check": False,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        # A name can be ambiguous: verify the open vault before dispatching.
        target = f"vault={vault.name}"
        info = subprocess.run([cli, target, "vault", "info=path"], **options)
        if info.returncode or Path(info.stdout.strip()).resolve() != vault.resolve():
            return "deferred"
        result = subprocess.run(
            [cli, target, "command", "id=remotely-save:start-sync"], **options
        )
        # Some CLI errors return zero. Require its explicit command acknowledgement.
        acknowledged = result.stdout.strip() in {
            "Executed: remotely-save:start-sync",
            "Executed command: remotely-save:start-sync",
        }
        return "requested" if result.returncode == 0 and acknowledged else "deferred"
    except (OSError, subprocess.SubprocessError, ValueError):
        return "deferred"


def sync(config, *, rename_note=None):
    vault = Path(config["vault"])
    if not vault.is_dir():
        raise ArchiveError("configured vault does not exist")
    archive = safe_path(vault, config.get("folder", "AI Conversations/Codex"))
    state_root = Path(config["state_dir"])
    state_path = safe_path(state_root, "manifest.json")
    with run_lock(safe_path(state_root, "export.lock")):
        state: ExportState = (
            json.loads(state_path.read_text(encoding="utf-8"))
            if state_path.exists()
            else {"files": {}}
        )
        labels, unsupported, unavailable = emdash_metadata(
            config.get("emdash_databases", [])
        )
        counts: ExportCounts = {
            "updated": 0,
            "unchanged": 0,
            "errors": 0,
            "renamed": 0,
            "unsupported_emdash": unsupported,
            "metadata_unavailable": unavailable,
            "partial_transcripts": 0,
        }
        sources = []
        codex_home = Path(config["codex_home"])
        for directory in (codex_home / "sessions", codex_home / "archived_sessions"):
            if directory.is_dir():
                sources.extend(directory.rglob("*.jsonl"))
        active_ids = set()
        selected_entries = {}
        for source in sorted(
            sources,
            key=lambda path: (
                path.relative_to(codex_home).parts[0] != "sessions",
                str(path),
            ),
        ):
            if source.is_symlink() or not source.resolve().is_relative_to(
                codex_home.resolve()
            ):
                counts["errors"] += 1
                continue
            key = str(source.resolve())
            entry = state["files"].get(key, {})
            if entry.get("session_id") in active_ids:
                continue
            try:
                stamp = source.stat()

                def signature(session_id, stamp=stamp):
                    label = labels.get(session_id, {})
                    return [
                        FORMAT_VERSION,
                        stamp.st_size,
                        stamp.st_mtime_ns,
                        hashlib.sha256(
                            json.dumps(label, sort_keys=True).encode()
                        ).hexdigest(),
                    ]

                fingerprint = signature(entry.get("session_id"))
                if (
                    entry.get("signature") == fingerprint
                    and safe_path(archive, entry["file"]).is_file()
                ):
                    counts["unchanged"] += 1
                    active_ids.add(entry["session_id"])
                    selected_entries[entry["session_id"]] = entry
                    continue
                conversation = parse_transcript(source)
                # Live and archived copies represent the same conversation, not separate notes.
                if conversation.session_id in active_ids:
                    continue
                active_ids.add(conversation.session_id)
                fingerprint = signature(conversation.session_id)
                content, title = render(
                    conversation, labels.get(conversation.session_id, {})
                )
                filename, renamed = name_note(
                    archive, entry, conversation.session_id, title, conversation.created,
                    rename_note,
                )
                changed = managed_write(
                    safe_path(archive, filename), conversation.session_id, content
                )
                counts["renamed"] += int(renamed)
                counts["updated" if changed or renamed else "unchanged"] += 1
                if conversation.malformed:
                    counts["partial_transcripts"] += 1
                state["files"][key] = {
                    "signature": None if conversation.malformed else fingerprint,
                    "session_id": conversation.session_id,
                    "file": filename,
                    "title": title,
                    "created": conversation.created,
                    "filename_version": FILENAME_VERSION,
                    "messages": len(conversation.messages),
                }
                selected_entries[conversation.session_id] = state["files"][key]
            except (ArchiveError, OSError, ValueError, TypeError):
                counts["errors"] += 1
        notes = {
            entry["session_id"]: entry
            for entry in state["files"].values()
            if "session_id" in entry
        }
        notes.update(selected_entries)
        # Retain and migrate owned notes even if their source transcript was removed.
        for session_id, entry in notes.items():
            if (
                entry.get("filename_version") != FILENAME_VERSION
                and session_id not in active_ids
            ):
                try:
                    old = safe_path(archive, entry["file"])
                    text = owned_note_text(old, session_id)
                    match = re.search(r"^- \*\*Created:\*\* (.+)$", text, re.MULTILINE)
                    created = entry.get("created") or (match[1] if match else "")
                    filename, renamed = name_note(
                        archive, entry, session_id, entry["title"], created, rename_note
                    )
                    entry.update(
                        file=filename, created=created, filename_version=FILENAME_VERSION
                    )
                    counts["renamed"] += int(renamed)
                    counts["updated"] += int(renamed)
                except (ArchiveError, OSError, ValueError, TypeError, KeyError):
                    counts["errors"] += 1
            for cached in state["files"].values():
                if cached.get("session_id") == session_id:
                    for field in ("file", "created", "filename_version"):
                        if field in entry:
                            cached[field] = entry[field]
        counts["emdash_without_local_transcript"] = len(set(labels) - set(notes))
        lines = [
            "# Codex and Emdash conversations",
            "",
            "Updated automatically from local Codex transcripts.",
            "",
            (
                "User/assistant messages only; Remotely Save cloud sync enabled. Redaction is best effort."
                if config.get("remotely_save_sync") is True
                else "User/assistant messages only; no API calls or model inference. Redaction is best effort."
            ),
            "",
            "Each note has a Personal notes section that the exporter preserves.",
            "",
        ]
        for _session_id, entry in sorted(
            notes.items(),
            key=lambda pair: (
                created_time(pair[1].get("created")) or datetime.max.replace(tzinfo=timezone.utc),
                pair[1]["file"].casefold(),
            ),
        ):
            title = entry["title"].replace("[", "(").replace("]", ")").replace("|", "-")
            stamp = created_time(entry.get("created"))
            date = stamp.strftime("%Y-%m-%d %H:%M:%S UTC") if stamp else "Unknown date"
            target = Path(entry["file"]).stem
            lines.append(
                f"- {date} — [[{target}|{title}]] — {entry['messages']} messages"
            )
        if unsupported:
            lines.extend(
                [
                    "",
                    f"{unsupported} Emdash records use non-Codex providers and require another exporter.",
                ]
            )
        if counts["emdash_without_local_transcript"]:
            lines.extend(
                [
                    "",
                    f"{counts['emdash_without_local_transcript']} Emdash Codex records have no available local transcript.",
                ]
            )
        index_changed = managed_write(
            safe_path(archive, "Index.md"), "index", "\n".join(lines)
        )
        if config.get("remotely_save_sync") is True:
            if counts["updated"] or index_changed or state.get("remote_sync_pending"):
                counts["remote_sync"] = request_remote_sync(vault)
                state["remote_sync_pending"] = counts["remote_sync"] != "requested"
            else:
                counts["remote_sync"] = "unchanged"
        atomic_write(state_path, json.dumps(state, indent=2) + "\n")
        counts["notes"] = len(notes)
        status = {**counts, "checked_at": datetime.now(timezone.utc).isoformat()}
        atomic_write(
            safe_path(state_root, "status.json"), json.dumps(status, indent=2) + "\n"
        )
        return status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Local installation JSON; never commit it",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Fallback mode: poll every minute until stopped",
    )
    args = parser.parse_args()
    while True:
        try:
            config = json.loads(args.config.read_text(encoding="utf-8"))
            if config.get("enabled", True) is False:
                return 0
            counts = sync(config)
            if sys.stdout:
                print(json.dumps(counts))
            result = 1 if counts["errors"] else 0
        except (ArchiveError, OSError, ValueError, KeyError, TypeError):
            if sys.stderr:
                print(
                    "Archive export could not complete; source conversations were not modified.",
                    file=sys.stderr,
                )
            result = 1
        if not args.watch:
            return result
        time.sleep(60)


if __name__ == "__main__":
    raise SystemExit(main())
