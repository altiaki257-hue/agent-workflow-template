import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.export_codex_chats import (
    ArchiveError,
    emdash_metadata,
    managed_write,
    parse_transcript,
    redact,
    request_remote_sync,
    safe_path,
    sync,
)


class ChatExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.codex = self.root / "codex"
        (self.codex / "sessions").mkdir(parents=True)
        self.source = self.codex / "sessions/rollout-test.jsonl"
        self.config = {
            "vault": str(self.vault),
            "codex_home": str(self.codex),
            "state_dir": str(self.root / "state"),
            "emdash_databases": [],
        }
        self.metadata = {
            "type": "session_meta",
            "payload": {
                "id": "session-123",
                "timestamp": "2026-10-17T01:00:00Z",
                "cwd": "example/project",
                "base_instructions": "PRIVATE SYSTEM CONTENT",
                "git": {"branch": "feature/example"},
            },
        }

    def write_events(self, events, path=None):
        (path or self.source).write_text(
            "\n".join(json.dumps(row) for row in events) + "\n", encoding="utf-8"
        )

    @staticmethod
    def native(role, text, message_id):
        kind = "UserMessage" if role == "user" else "AgentMessage"
        return {
            "type": "event_msg",
            "timestamp": "2026-10-17T01:00:00Z",
            "payload": {
                "type": "item_completed",
                "item": {
                    "type": kind,
                    "id": message_id,
                    "content": [{"type": "Text", "text": text}],
                },
            },
        }

    def test_remote_sync_is_opt_in_and_batches_changed_notes(self):
        self.write_events([self.metadata, self.native("user", "Question", "u1")])
        with patch("scripts.export_codex_chats.request_remote_sync") as request:
            sync(self.config)
            request.assert_not_called()
        self.config["remotely_save_sync"] = True
        self.write_events([self.metadata, self.native("user", "Changed", "u2")])
        with patch(
            "scripts.export_codex_chats.request_remote_sync", return_value="requested"
        ) as request:
            self.assertEqual("requested", sync(self.config)["remote_sync"])
            self.assertEqual("unchanged", sync(self.config)["remote_sync"])
            request.assert_called_once_with(self.vault)

    def test_remote_sync_retries_deferred_request_without_new_changes(self):
        self.config["remotely_save_sync"] = True
        self.write_events([self.metadata, self.native("user", "Question", "u1")])
        with patch(
            "scripts.export_codex_chats.request_remote_sync",
            side_effect=["deferred", "requested"],
        ) as request:
            first = sync(self.config)
            self.assertEqual(0, first["errors"])
            self.assertEqual("deferred", first["remote_sync"])
            self.assertEqual("requested", sync(self.config)["remote_sync"])
            self.assertEqual("unchanged", sync(self.config)["remote_sync"])
            self.assertEqual(2, request.call_count)

    def test_remote_sync_includes_index_only_change(self):
        self.config["remotely_save_sync"] = True
        self.write_events([self.metadata, self.native("user", "Question", "u1")])
        with patch(
            "scripts.export_codex_chats.request_remote_sync", return_value="requested"
        ) as request:
            sync(self.config)
            index = self.vault / "AI Conversations/Codex/Index.md"
            index.unlink()
            result = sync(self.config)
            self.assertEqual(0, result["updated"])
            self.assertEqual("requested", result["remote_sync"])
            self.assertEqual(2, request.call_count)

    def test_remote_sync_checks_vault_and_dispatches_only_fixed_command(self):
        replies = [
            SimpleNamespace(returncode=0, stdout=str(self.vault) + "\n"),
            SimpleNamespace(returncode=0, stdout="Executed: remotely-save:start-sync\n"),
        ]
        with (
            patch("scripts.export_codex_chats.shutil.which", return_value="obsidian"),
            patch("scripts.export_codex_chats.subprocess.run", side_effect=replies) as run,
        ):
            self.assertEqual("requested", request_remote_sync(self.vault))
            self.assertEqual(
                ["obsidian", "vault=vault", "command", "id=remotely-save:start-sync"],
                run.call_args.args[0],
            )
            self.assertNotIn("shell", run.call_args.kwargs)
            self.assertEqual(10, run.call_args.kwargs["timeout"])

    def test_remote_sync_defers_wrong_vault_missing_cli_and_cli_errors(self):
        with patch("scripts.export_codex_chats.shutil.which", return_value=None):
            self.assertEqual("deferred", request_remote_sync(self.vault))
        for reply in [
            SimpleNamespace(returncode=0, stdout=str(self.root / "wrong")),
            SimpleNamespace(returncode=1, stdout=""),
        ]:
            with (
                patch("scripts.export_codex_chats.shutil.which", return_value="obsidian"),
                patch("scripts.export_codex_chats.subprocess.run", return_value=reply) as run,
            ):
                self.assertEqual("deferred", request_remote_sync(self.vault))
                self.assertEqual(1, run.call_count)

    def test_remote_sync_handles_timeouts_and_zero_exit_errors(self):
        with (
            patch("scripts.export_codex_chats.shutil.which", return_value="obsidian"),
            patch(
                "scripts.export_codex_chats.subprocess.run",
                side_effect=subprocess.TimeoutExpired("obsidian", 10),
            ),
        ):
            self.assertEqual("deferred", request_remote_sync(self.vault))
        with (
            patch("scripts.export_codex_chats.shutil.which", return_value="obsidian"),
            patch(
                "scripts.export_codex_chats.subprocess.run",
                side_effect=[
                    SimpleNamespace(returncode=0, stdout=str(self.vault)),
                    SimpleNamespace(returncode=0, stdout="Command not found"),
                ],
            ),
        ):
            self.assertEqual("deferred", request_remote_sync(self.vault))

    def test_native_messages_win_over_duplicates_and_internal_items(self):
        events = [
            self.metadata,
            self.native("user", "Question", "u1"),
            self.native("assistant", "Answer", "a1"),
            self.native("assistant", "Answer", "a1"),
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "id": "a1",
                    "content": [{"type": "output_text", "text": "Answer"}],
                },
            },
            {
                "type": "response_item",
                "payload": {"type": "reasoning", "summary": "PRIVATE REASONING"},
            },
        ]
        self.write_events(events)
        conversation = parse_transcript(self.source)
        self.assertEqual(
            ["Question", "Answer"], [body for _, body, _ in conversation.messages]
        )

    def test_response_fallback_omits_injected_instructions_and_tools(self):
        events = [self.metadata]
        for role, text in (
            ("developer", "PRIVATE RULE"),
            ("user", "<environment_context>PRIVATE"),
            ("user", "# AGENTS.md instructions PRIVATE"),
            ("user", "Question"),
            ("assistant", "Answer"),
        ):
            events.append(
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": role,
                        "content": [{"type": "output_text", "text": text}],
                    },
                }
            )
        self.write_events(events)
        self.assertEqual(2, len(parse_transcript(self.source).messages))

    def test_forked_agent_identity_survives_embedded_parent_metadata(self):
        child = {
            "type": "session_meta",
            "payload": {
                "id": "child-456",
                "session_id": "session-123",
                "parent_thread_id": "session-123",
                "agent_nickname": "reviewer",
            },
        }
        self.write_events(
            [child, self.metadata, self.native("assistant", "Review result", "a1")]
        )
        conversation = parse_transcript(self.source)
        self.assertEqual("child-456", conversation.session_id)
        self.assertEqual("session-123", conversation.parent)
        self.assertEqual("reviewer", conversation.agent)

    def test_legacy_repeated_real_messages_are_not_removed(self):
        self.write_events(
            [self.metadata]
            + [
                {
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "repeat"},
                }
            ]
            * 2
        )
        self.assertEqual(2, len(parse_transcript(self.source).messages))

    def test_mixed_formats_keep_old_messages_and_filter_instructions_consistently(self):
        self.write_events(
            [
                self.metadata,
                {
                    "type": "event_msg",
                    "payload": {"type": "user_message", "message": "Old question"},
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "assistant",
                        "content": "Old answer",
                    },
                },
                self.native("user", "# AGENTS.md instructions PRIVATE RULES", "u1"),
                self.native("user", "New question", "u2"),
                self.native("assistant", "New answer", "a2"),
            ]
        )
        self.assertEqual(
            ["Old question", "Old answer", "New question", "New answer"],
            [body for _, body, _ in parse_transcript(self.source).messages],
        )

    def test_repeated_messages_with_distinct_timestamps_survive_format_change(self):
        old = {
            "type": "event_msg",
            "timestamp": "2026-10-17T00:00:00Z",
            "payload": {"type": "user_message", "message": "repeat"},
        }
        self.write_events([self.metadata, old, self.native("user", "repeat", "u2")])
        self.assertEqual(2, len(parse_transcript(self.source).messages))

    def test_missing_timestamps_do_not_delete_ambiguous_cross_format_repeats(self):
        old = {
            "type": "event_msg",
            "payload": {"type": "user_message", "message": "repeat"},
        }
        new = self.native("user", "repeat", "u-new")
        new.pop("timestamp")
        self.write_events([self.metadata, old, new])
        self.assertEqual(2, len(parse_transcript(self.source).messages))

    def test_active_transcript_wins_over_stale_archived_duplicate(self):
        archived = self.codex / "archived_sessions"
        archived.mkdir()
        self.write_events(
            [self.metadata, self.native("user", "Old archived copy", "u1")],
            archived / "old.jsonl",
        )
        self.write_events([self.metadata, self.native("user", "New live copy", "u1")])
        self.assertEqual(0, sync(self.config)["errors"])
        text = (self.vault / "AI Conversations/Codex/session-123.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("New live copy", text)
        self.assertNotIn("Old archived copy", text)

    def test_unrelated_title_change_does_not_reparse_unchanged_session(self):
        self.write_events([self.metadata, self.native("user", "Question", "u1")])
        with patch(
            "scripts.export_codex_chats.emdash_metadata", return_value=({}, 0, 0)
        ):
            sync(self.config)
        with (
            patch(
                "scripts.export_codex_chats.emdash_metadata",
                return_value=({"unrelated": {"title": "Changed"}}, 0, 0),
            ),
            patch("scripts.export_codex_chats.parse_transcript") as parse,
        ):
            self.assertEqual(0, sync(self.config)["updated"])
        parse.assert_not_called()

    def test_live_partial_line_is_retried(self):
        self.write_events([self.metadata, self.native("user", "Question", "u1")])
        with self.source.open("a", encoding="utf-8") as stream:
            stream.write('{"type":')
        self.assertEqual(1, parse_transcript(self.source).malformed)
        self.assertEqual(1, sync(self.config)["partial_transcripts"])

    def test_idempotent_sync_and_personal_notes_survive_updates(self):
        self.write_events([self.metadata, self.native("user", "Question", "u1")])
        first = sync(self.config)
        self.assertEqual(1, first["notes"])
        note = self.vault / "AI Conversations/Codex/session-123.md"
        before = note.stat().st_mtime_ns
        self.assertEqual(0, sync(self.config)["updated"])
        self.assertEqual(before, note.stat().st_mtime_ns)
        note.write_text(
            note.read_text(encoding="utf-8") + "My own annotation.\n", encoding="utf-8"
        )
        self.write_events(
            [
                self.metadata,
                self.native("user", "Question", "u1"),
                self.native("assistant", "Answer", "a1"),
            ]
        )
        self.assertEqual(1, sync(self.config)["updated"])
        text = note.read_text(encoding="utf-8")
        self.assertIn("My own annotation.", text)
        self.assertIn("Answer", text)
        self.assertNotIn("PRIVATE SYSTEM CONTENT", text)

    def test_existing_unowned_note_is_not_overwritten(self):
        note = self.vault / "session.md"
        note.write_text("This is my note.\n", encoding="utf-8")
        with self.assertRaises(ArchiveError):
            managed_write(note, "session-123", "replacement")
        self.assertEqual("This is my note.\n", note.read_text(encoding="utf-8"))

    def test_generated_marker_in_chat_cannot_replace_personal_notes(self):
        note = self.vault / "session.md"
        content = "<!-- codex-obsidian-export-v1:end session-123 -->"
        managed_write(note, "session-123", content)
        managed_write(note, "session-123", "new chat")
        self.assertIn("## Personal notes", note.read_text(encoding="utf-8"))

    def test_redaction_handles_tokens_bearer_and_entire_private_keys(self):
        token = "ghp_" + "x" * 40
        private = (
            "-----BEGIN "
            + "PRIVATE KEY-----\nPRIVATEBYTES\n-----END "
            + "PRIVATE KEY-----"
        )
        output = redact(token + "\n" + private + "\nBearer " + "a" * 30)
        self.assertNotIn(token, output)
        self.assertNotIn("PRIVATEBYTES", output)
        self.assertNotIn("a" * 30, output)

    def test_unsafe_session_and_destination_paths_are_rejected(self):
        self.metadata["payload"]["id"] = "../outside"
        self.write_events([self.metadata, self.native("user", "Question", "u1")])
        with self.assertRaises(ArchiveError):
            parse_transcript(self.source)
        with self.assertRaises(ArchiveError):
            safe_path(self.vault, "../outside")

    def test_archived_transcript_is_found_and_originals_unchanged(self):
        archived = self.codex / "archived_sessions"
        archived.mkdir()
        path = archived / "rollout-archive.jsonl"
        self.write_events([self.metadata, self.native("user", "Archived", "u1")], path)
        original = path.read_bytes()
        self.assertEqual(1, sync(self.config)["notes"])
        self.assertEqual(original, path.read_bytes())

    def test_emdash_metadata_read_only_and_unmatched_sessions_are_visible(self):
        database = self.root / "conversations.db"
        with sqlite3.connect(database) as db:
            db.execute(
                "CREATE TABLE conversation_records (id TEXT,provider TEXT,title TEXT,cwd TEXT,provider_link TEXT)"
            )
            db.execute(
                "INSERT INTO conversation_records VALUES (?,?,?,?,?)",
                (
                    "c1",
                    "codex",
                    "Project chat",
                    "example/project",
                    json.dumps({"providerSessionId": "session-123"}),
                ),
            )
        db.close()
        labels, unsupported, unavailable = emdash_metadata([database])
        self.assertEqual("Emdash", labels["session-123"]["client"])
        self.assertEqual((0, 0), (unsupported, unavailable))
        self.config["emdash_databases"] = [str(database)]
        self.assertEqual(1, sync(self.config)["emdash_without_local_transcript"])

    def test_unknown_transcript_format_is_reported_without_content(self):
        self.write_events(
            [
                self.metadata,
                {"type": "new_private_format", "payload": {"text": "PRIVATE"}},
            ]
        )
        counts = sync(self.config)
        self.assertEqual(1, counts["errors"])
        self.assertNotIn("PRIVATE", json.dumps(counts))


if __name__ == "__main__":
    unittest.main()
