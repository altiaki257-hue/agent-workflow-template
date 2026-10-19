"""Offline repository lint and safety checks. Uses only the Python standard library."""

import ast
import fnmatch
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ROLES = {
    "researcher": "deny",
    "test-designer": "deny",
    "junior-developer": "ask",
    "answer-coordinator": "deny",
    "answer-critic": "deny",
}
DIRECT_PROVIDER_MODELS = {
    "groq": {"openai/gpt-oss-120b", "qwen/qwen3.8-27b"},
    "google": {"gemini-3.1-flash-lite"},
}
# Primary and one runner-up per role. This reviewed table also drives bridge routing.
ROLE_MODELS = {
    "answer-coordinator": (
        "groq/openai/gpt-oss-120b",
        "openrouter/cohere/north-mini-code:free",
    ),
    "answer-critic": (
        "groq/qwen/qwen3.8-27b",
        "openrouter/cohere/north-mini-code:free",
    ),
    "researcher": ("google/gemini-3.1-flash-lite", "groq/openai/gpt-oss-120b"),
    "test-designer": (
        "openrouter/cohere/north-mini-code:free",
        "groq/openai/gpt-oss-120b",
    ),
    "junior-developer": (
        "groq/qwen/qwen3.8-27b",
        "openrouter/cohere/north-mini-code:free",
    ),
}

REQUIRED = (
    "AGENTS.md",
    "CLAUDE.md",
    "docs/architecture.md",
    "docs/project-status.md",
    "docs/technical-decisions.md",
    "docs/known-issues.md",
    "docs/workflow.md",
    "tasks/backlog.md",
    "tasks/contracts/TEMPLATE.md",
    "tasks/handoffs/TEMPLATE.md",
    "opencode.json",
    ".github/workflows/ci.yml",
)
SECRET_PATTERNS = {
    "AWS access key": re.compile(rb"(?:AKIA|ASIA)[A-Z0-9]{16}"),
    "provider API key": re.compile(
        rb"sk-(?:or-v1-|ant-api\d+-|proj-)[A-Za-z0-9_-]{20,}"
    ),
    "Groq API key": re.compile(rb"gsk_[A-Za-z0-9_-]{20,}"),
    "Google API key": re.compile(rb"AIza[A-Za-z0-9_-]{35}"),
    "GitHub token": re.compile(rb"(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}"),
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
    ),
    "credential URL": re.compile(rb"https?://[^\s/:@]{2,}:[^\s/@]{4,}@"),
}


def permission_for(config, agent_name, tool, resource="*"):
    """Evaluate this repo's v1 wildcard rules, in global then agent order."""
    action = "allow"
    for rules in (
        config.get("permission", {}),
        config.get("agent", {}).get(agent_name, {}).get("permission", {}),
    ):
        if isinstance(rules, str):
            action = rules
            continue
        for tool_pattern, value in rules.items():
            if not fnmatch.fnmatchcase(tool, tool_pattern):
                continue
            if isinstance(value, str):
                action = value
            else:
                for pattern, effect in value.items():
                    if fnmatch.fnmatchcase(resource, pattern):
                        action = effect
    return action


def config_errors(config):
    errors = []
    router = config.get("provider", {}).get("openrouter", {})
    models = router.get("models", {})
    if set(router) - {"whitelist", "models"}:
        errors.append("unreviewed OpenRouter provider or endpoint override")
    providers = config.get("provider", {})
    enabled = config.get("enabled_providers", [])
    if (
        not isinstance(enabled, list)
        or set(enabled) != set(providers)
        or len(enabled) != len(set(enabled))
    ):
        errors.append(
            "enabled providers must exactly match reviewed provider definitions"
        )
    if "openrouter" not in providers or set(providers) - {
        "openrouter",
        *DIRECT_PROVIDER_MODELS,
    }:
        errors.append("unexpected provider configuration")
    for provider, permitted in DIRECT_PROVIDER_MODELS.items():
        if provider not in providers:
            continue
        details = providers[provider]
        direct_models = details.get("models", {})
        whitelist = details.get("whitelist", [])
        if (
            set(details) != {"whitelist", "models"}
            or not direct_models
            or set(whitelist) != set(direct_models)
            or len(whitelist) != len(set(whitelist))
            or set(direct_models) - permitted
        ):
            errors.append(f"{provider}: only reviewed model allowlists are permitted")
        if any(set(model) != {"name"} for model in direct_models.values()):
            errors.append(
                f"{provider}: SDK, endpoint, pricing and request overrides are forbidden"
            )
    if not models or set(router.get("whitelist", [])) != set(models):
        errors.append("model whitelist must exactly match configured free endpoints")
    allowed = {"openrouter/" + model for model in models}
    role_allowed = allowed | {
        provider + "/" + model
        for provider in DIRECT_PROVIDER_MODELS
        for model in providers.get(provider, {}).get("models", {})
    }
    for field in ("model", "small_model"):
        if config.get(field) not in allowed:
            errors.append(f"{field} must explicitly select an approved free endpoint")
    for model, details in models.items():
        if set(details) - {"name", "options"}:
            errors.append("model ID, SDK, and endpoint aliases require explicit review")
        if set(details.get("options", {})) - {"provider"}:
            errors.append("unreviewed model request options")
        routing = details.get("options", {}).get("provider", {})
        if not model.endswith(":free"):
            errors.append("a configured model is not an explicit free endpoint")
        if routing.get("allow_fallbacks") is not False:
            errors.append("provider fallbacks must be disabled")
        if routing.get("max_price") != {"prompt": 0, "completion": 0, "request": 0}:
            errors.append("zero price limits are required")
        if "plugins" in details.get("options", {}) or "models" in details.get(
            "options", {}
        ):
            errors.append("paid plugins and model fallback lists are not allowed")
    if (
        config.get("share") != "disabled"
        or config.get("default_agent") != "answer-coordinator"
    ):
        errors.append("default agent must be read-only and session sharing disabled")
    if config.get("subagent_depth") != 1:
        errors.append("nested agent delegation must be disabled")
    bridge = config.get("mcp", {}).get("answer_team", {})
    if (
        bridge.get("type") != "local"
        or bridge.get("command") != ["python", "scripts/answer_team.py", "--mcp"]
        or bridge.get("timeout") != 300000
        or not isinstance(bridge.get("enabled"), bool)
        or set(bridge) - {"type", "command", "timeout", "enabled"}
    ):
        errors.append(
            "answer-team MCP command and bounded timeout must match reviewed configuration"
        )
    for name, server in config.get("mcp", {}).items():
        if name != "answer_team" and (
            not isinstance(server, dict) or server.get("enabled") is not False
        ):
            errors.append(
                "unreviewed enabled MCP server must not start inside answer workers"
            )
    if config.get("permission", {}).get("*") != "deny":
        errors.append("unrecognized tools, including MCP tools, must default to deny")
    for name in ("build", "plan", "general", "explore"):
        if config.get("agent", {}).get(name, {}).get("disable") is not True:
            errors.append(f"built-in {name} agent must be disabled")
    agents = config.get("agent", {})
    known_permissions = {
        "*",
        "read",
        "edit",
        "bash",
        "glob",
        "grep",
        "list",
        "question",
        "task",
        "external_directory",
        "webfetch",
        "websearch",
        "doom_loop",
    }
    for rules in [config.get("permission", {})] + [
        a.get("permission", {}) for a in agents.values()
    ]:
        if isinstance(rules, dict) and any(
            key not in known_permissions | {"answer_team_ask_team"} and value != "deny"
            for key, value in rules.items()
        ):
            errors.append("unreviewed custom/MCP tool permission")
    for name, agent in agents.items():
        if agent.get("disable"):
            continue
        if name not in ROLES:
            errors.append(f"unreviewed agent definition: {name}")
        if set(agent) - {
            "description",
            "mode",
            "model",
            "steps",
            "prompt",
            "permission",
            "disable",
            "options",
        }:
            errors.append(f"{name}: unreviewed agent request options")
        if agent.get("options"):
            errors.append(
                f"{name}: provider options must come only from reviewed model configuration"
            )
    for name, edit_action in ROLES.items():
        agent = agents.get(name, {})
        if (
            agent.get("model") != ROLE_MODELS[name][0]
            or agent.get("model") not in role_allowed
            or ROLE_MODELS[name][1] not in role_allowed
            or not 1 <= agent.get("steps", 0) <= 12
        ):
            errors.append(f"{name}: explicit free model and bounded steps required")
        expected_mode = "primary" if name == "answer-coordinator" else "all"
        if agent.get("mode") != expected_mode:
            errors.append(f"{name}: incorrect role mode")
        for tool, expected in (
            ("edit", edit_action),
            ("bash", edit_action),
            ("external_directory", "deny"),
            ("serena_execute_shell_command", "deny"),
        ):
            if permission_for(config, name, tool) != expected:
                errors.append(f"{name}: unsafe {tool} permission")
        for target in (*ROLES, "build", "general", "explore", "new-unsafe-agent"):
            expected = "deny"
            if permission_for(config, name, "task", target) != expected:
                errors.append(f"{name}: unsafe delegation to {target}")
        expected_bridge = "allow" if name == "answer-coordinator" else "deny"
        if permission_for(config, name, "answer_team_ask_team") != expected_bridge:
            errors.append(f"{name}: unsafe answer-team bridge access")
        if name == "answer-coordinator":
            critic_model = agents.get("answer-critic", {}).get("model")
            if critic_model == agent.get("model"):
                errors.append("answer critique must use a distinct approved free model")
        for command in (
            "python -m unittest",
            "git diff --output=example.txt",
            "rg --pre example .",
            "git push",
            "git commit",
        ):
            if permission_for(config, name, "bash", command) != edit_action:
                errors.append(f"{name}: shell command bypasses role approval")
        expected_web = {"ask", "deny"} if name == "researcher" else {"deny"}
        for tool in ("webfetch", "websearch"):
            if permission_for(config, name, tool) not in expected_web:
                errors.append(f"{name}: unsafe web access")
        for sensitive in (
            ".env",
            "nested/.env.prod",
            "server.key",
            ".aws/credentials",
            ".opencode/auth.json",
            ".claude/settings.local.json",
            ".serena/project.local.yml",
            ".ssh/id_ed25519",
            ".netrc",
            ".secrets/production.json",
        ):
            if permission_for(config, name, "read", "/checkout/" + sensitive) != "deny":
                errors.append(f"{name}: credential reads must be denied")
    return sorted(set(errors))


def repository_files(root):
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return sorted({os.fsdecode(name) for name in result.stdout.split(b"\0") if name})


def sensitive_name(relative):
    path = Path(relative)
    name = path.name.lower()
    parts = {part.lower() for part in path.parts[:-1]}
    if name.endswith(".env.example"):
        return False
    return (
        name == ".env"
        or name.startswith(".env.")
        or name.endswith(".env")
        or ".env." in name
        or name.endswith((".pem", ".key", ".p12", ".pfx", ".jks", ".keystore"))
        or name in {".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519"}
        or name.startswith(("credentials", "service-account", "secrets."))
        or bool(parts & {".aws", ".ssh", ".secrets"})
        or (name == "auth.json" and bool(parts & {".opencode", ".codex"}))
        or (name == "settings.local.json" and ".claude" in parts)
        or (name == "project.local.yml" and ".serena" in parts)
    )


def scan_file(root, relative):
    """Scan bytes in bounded chunks; never include content in findings."""
    path = root / relative
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        return [f"{relative!r}: symlink or path outside checkout requires review"]
    if not path.is_file():
        return []  # Deleted tracked files and submodule directories.
    findings = (
        [f"{relative!r}: sensitive filename must not be tracked"]
        if sensitive_name(relative)
        else []
    )
    matched = set()
    overlap = b""
    with path.open("rb") as stream:
        while chunk := stream.read(65536):
            block = overlap + chunk
            matched.update(
                label
                for label, pattern in SECRET_PATTERNS.items()
                if pattern.search(block)
            )
            overlap = block[-1024:]
    findings.extend(f"{relative!r}: possible {label}" for label in sorted(matched))
    return findings


def lint_file(root, relative):
    path = root / relative
    if path.suffix not in {
        ".md",
        ".json",
        ".yml",
        ".yaml",
        ".py",
    } and path.name not in {
        ".gitattributes",
        ".gitignore",
        ".editorconfig",
    }:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeError, OSError):
        return [f"{relative!r}: expected readable UTF-8 text"]
    errors = []
    if not text.endswith("\n") or any(
        line != line.rstrip() for line in text.splitlines()
    ):
        errors.append(f"{relative!r}: missing final newline or trailing whitespace")
    if path.suffix == ".py":
        try:
            ast.parse(text, filename=relative)
        except SyntaxError:
            errors.append(f"{relative!r}: invalid Python syntax")
    if path.suffix == ".json":
        try:
            json.loads(text)
        except ValueError:
            errors.append(f"{relative!r}: invalid JSON")
    if path.suffix == ".md":
        # Templates intentionally contain placeholders, so validate concrete relative links only.
        for target in re.findall(r"\]\(([^\s)]+)\)", text):
            if (
                any(char in target for char in "<>{}")
                or urlsplit(target).scheme
                or target.startswith("#")
            ):
                continue
            destination = unquote(target.split("#", 1)[0])
            resolved = (path.parent / destination).resolve()
            if not resolved.is_relative_to(root.resolve()) or not resolved.exists():
                errors.append(f"{relative!r}: broken or external local link")
    return errors


def validate(root=ROOT):
    errors = [
        f"missing required file: {name}"
        for name in REQUIRED
        if not (root / name).is_file()
    ]
    try:
        config = json.loads((root / "opencode.json").read_text(encoding="utf-8"))
        errors.extend(config_errors(config))
        for role in ROLES:
            prompt = config.get("agent", {}).get(role, {}).get("prompt", "")
            match = re.fullmatch(r"\{file:\./(\.opencode/prompts/[\w-]+\.md)\}", prompt)
            if not match or not (root / match[1]).is_file():
                errors.append(f"{role}: missing local prompt")
            backup_path = root / f".opencode/commands/{role}-backup.md"
            expected = f"agent: {role}\nmodel: {ROLE_MODELS[role][1]}\n"
            if not backup_path.is_file() or expected not in backup_path.read_text(
                encoding="utf-8"
            ):
                errors.append(
                    f"{role}: backup command must match reviewed role/model pair"
                )
    except (ValueError, OSError, TypeError, AttributeError):
        errors.append("cannot validate OpenCode configuration; check JSON structure")
    for relative in repository_files(root):
        findings = scan_file(root, relative)
        errors.extend(findings)
        if not findings and (root / relative).is_file():
            errors.extend(lint_file(root, relative))
    return errors


def main():
    try:
        errors = validate()
    except (OSError, subprocess.CalledProcessError):
        print(
            "Repository validation could not complete; check Git and file permissions.",
            file=sys.stderr,
        )
        return 1
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print("Repository policy, text lint, local links, and secret checks passed.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
