"""Configure owned Obsidian templates/navigation without reading private notes."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
FOLDER = "Projects/Agent Workflow"
START = "<!-- agent-workflow:begin -->"
END = "<!-- agent-workflow:end -->"


def safe_path(vault, relative):
    relative = Path(relative)
    target = vault / relative
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Note path must stay inside the vault.")
    if not target.resolve().is_relative_to(vault.resolve()) or target.is_symlink():
        raise ValueError("Note path escapes the vault or is a symlink.")
    return target


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".agent-notes-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def managed_note(path, generated, metadata=None):
    block = START + "\n" + generated.rstrip() + "\n" + END
    if path.exists():
        before = path.read_text(encoding="utf-8")
        if before.count(START) != 1 or before.count(END) != 1:
            raise ValueError(
                "Existing note has no unique ownership markers; preserved."
            )
        start = before.index(START)
        end = before.index(END) + len(END)
        if end <= start:
            raise ValueError("Invalid note ownership markers; preserved.")
        prefix = before[:start]
        if metadata:
            if not prefix.startswith("---\n") or "\n---\n" not in prefix:
                raise ValueError("Managed note metadata is malformed; preserved.")
            header, remainder = prefix[4:].split("\n---\n", 1)
            lines = header.splitlines()
            seen = set()
            for line in lines:
                if not line or line.startswith("#"):
                    continue
                match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*): *(.*)", line)
                if not match or match[1] in seen:
                    raise ValueError("Unsupported note property syntax; preserved.")
                seen.add(match[1])
                if match[1] in metadata and not re.fullmatch(
                    r"[A-Za-z0-9_./:@+\-]+", match[2]
                ):
                    raise ValueError(
                        "Managed property is not a plain scalar; preserved."
                    )
            for key, value in metadata.items():
                positions = [
                    i for i, line in enumerate(lines) if line.startswith(key + ":")
                ]
                if len(positions) > 1:
                    raise ValueError("Duplicate managed note property; preserved.")
                if positions:
                    lines[positions[0]] = f"{key}: {value}"
                else:
                    lines.append(f"{key}: {value}")
            prefix = "---\n" + "\n".join(lines) + "\n---\n" + remainder
        text = prefix + block + before[end:]
    else:
        prefix = (
            "---\n" + "\n".join(f"{k}: {v}" for k, v in metadata.items()) + "\n---\n\n"
            if metadata
            else ""
        )
        text = prefix + block + "\n\n## Personal notes\n\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        atomic_write(path, text)


def configure(vault, project=ROOT, backup_root=None):
    vault = vault.resolve()
    if not vault.is_dir() or not (vault / ".obsidian").is_dir():
        raise ValueError("Select an existing Obsidian vault.")
    backup = (
        Path(backup_root)
        if backup_root
        else (
            Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir()))
            / "EmdashAgentSetup/backups"
            / ("notes-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        )
    )

    def settings(name, update):
        path = safe_path(vault, ".obsidian/" + name)
        before = path.read_bytes() if path.exists() else None
        data = json.loads(before) if before is not None else {}
        if not isinstance(data, dict):
            raise ValueError("Existing settings must be a JSON object; preserved.")
        if name == "types.json" and not isinstance(data.get("types", {}), dict):
            raise ValueError(
                "Existing property types must be a JSON object; preserved."
            )
        update(data)
        text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
        if before is not None and json.loads(before) == data:
            return data
        if before is not None:
            backup.mkdir(parents=True, exist_ok=True)
            (backup / name).write_bytes(before)
        atomic_write(path, text)
        return data

    templates = settings(
        "templates.json",
        lambda data: data.setdefault("folder", "Templates/Agent Workflow"),
    )
    template_folder = templates.get("folder")
    if not isinstance(template_folder, str) or not template_folder:
        raise ValueError(
            "Existing template folder is invalid; inspect it before changing."
        )
    folder = safe_path(vault, template_folder)
    for source in (ROOT / "assets/notes").glob("*.md"):
        destination = safe_path(vault, str(folder.relative_to(vault) / source.name))
        if not destination.exists():
            atomic_write(destination, source.read_text(encoding="utf-8"))
    settings(
        "core-plugins.json",
        lambda data: data.update(
            {"templates": True, "properties": True, "bases": True}
        ),
    )
    settings(
        "types.json",
        lambda data: [
            data.setdefault("types", {}).setdefault(key, value)
            for key, value in {
                "project": "text",
                "type": "text",
                "status": "text",
                "updated": "date",
                "source": "text",
            }.items()
        ],
    )
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    date = datetime.now(timezone.utc).date().isoformat()
    base = f"https://github.com/example-org/agent-workflow-template/blob/{commit}"
    metadata = {
        "project": "agent-workflow",
        "type": "project-brief",
        "status": "reference",
        "updated": date,
        "source": f"{base}/docs/project-status.md",
        "source_commit": commit,
    }
    managed_note(
        safe_path(vault, FOLDER + "/Project brief.md"),
        "# Agent workflow\n\nReusable agent-workflow infrastructure; no product application selected.\n\n"
        + f"- [Current project status]({base}/docs/project-status.md)\n"
        + f"- [Architecture]({base}/docs/architecture.md)\n"
        + f"- [Decisions]({base}/docs/technical-decisions.md)\n"
        + f"- [Active work and handoffs]({base}/tasks/backlog.md)\n\n"
        + "Git records are authoritative. These links describe the recorded commit; verify current history before acting.\n"
        + "Conversation archives are historical evidence and are excluded from routine project-note retrieval.\n\n"
        + "[[Projects/Agent Workflow/Notes dashboard.base|Notes dashboard]]\n",
        metadata,
    )
    dashboard = safe_path(vault, FOLDER + "/Notes dashboard.base")
    if not dashboard.exists():
        atomic_write(
            dashboard,
            (ROOT / "assets/notes/Notes dashboard.base").read_text(encoding="utf-8"),
        )
    return {
        "configured": True,
        "project_folder": FOLDER,
        "source_commit": commit,
        "backup": str(backup),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(configure(args.vault)))
    except (OSError, ValueError, subprocess.SubprocessError):
        print("Note setup failed; existing unowned notes were preserved.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
