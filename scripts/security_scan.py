"""Install a checksum-pinned native scanner or run the repository's local rules."""

import argparse
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.31.0"
# SHA256 digests from the official v1.31.0 GitHub release asset metadata.
ASSETS = {
    ("Windows", "amd64"): (
        "opengrep_windows_x86.exe",
        "fdd2e22549e7000ceb66976a01366db6910760b2aa4e457b6bda62545070d26a",
    ),
    ("Linux", "x86_64"): (
        "opengrep_manylinux_x86",
        "dbbe3c2058dbe600c449a8ba22ea79a1643a6660658400090d0323a8d0d31147",
    ),
    ("Linux", "aarch64"): (
        "opengrep_manylinux_aarch64",
        "2b713a29a00237f85408b83002fc111db5b94c7fa8d263f0a93184a960655d9d",
    ),
}


def selected_asset():
    key = (platform.system(), platform.machine().lower())
    if key not in ASSETS:
        raise ValueError("Unsupported scanner platform; no binary was selected.")
    return ASSETS[key]


def install_root():
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".cache")))
    return base / "EmdashSecurity" / "opengrep" / VERSION


def binary_path(directory):
    asset, _ = selected_asset()
    return directory / ("opengrep.exe" if asset.endswith(".exe") else "opengrep")


def verified_binary(directory):
    path = binary_path(directory)
    _, expected = selected_asset()
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Scanner missing or checksum mismatch; run install explicitly.")
    return path


def install(directory):
    directory = directory.resolve()
    if directory.is_relative_to(ROOT) or any(
        (parent / ".git").exists() for parent in (directory, *directory.parents)
    ):
        raise ValueError("Install the scanner outside Git worktrees.")
    asset, expected = selected_asset()
    path = binary_path(directory)
    if path.exists():
        return verified_binary(directory)
    directory.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/opengrep/opengrep/releases/download/v{VERSION}/{asset}"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=directory, delete=False) as stream:
            temporary = Path(stream.name)
            digest = hashlib.sha256()
            total = 0
            with urllib.request.urlopen(url, timeout=60) as response:
                if not response.url.startswith("https://"):
                    raise ValueError("Scanner download must retain HTTPS.")
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 128 * 1024 * 1024:
                        raise ValueError("Scanner download exceeded size limit.")
                    digest.update(block)
                    stream.write(block)
        if digest.hexdigest() != expected:
            raise ValueError("Downloaded scanner checksum mismatch; installation refused.")
        temporary.chmod(0o755)
        # Atomic publication without replacing an existing owner file.
        os.link(temporary, path)
        return verified_binary(directory)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def scan(mode, directory):
    executable = verified_binary(directory)
    command = [
        str(executable), "scan", "--strict", "--disable-version-check",
        "--config", ".semgrep/agent-security.yml",
    ]
    command += (
        ["--test", ".semgrep/agent-security.py"]
        if mode == "controls"
        else ["--error", "scripts"]
    )
    return subprocess.run(command, cwd=ROOT, check=False, timeout=180).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("install", "controls", "scan"))
    args = parser.parse_args()
    try:
        if args.mode == "install":
            install(install_root())
            print(f"Verified Opengrep {VERSION} installed.")
            return 0
        return scan(args.mode, install_root())
    except (OSError, ValueError, subprocess.SubprocessError):
        print("Security scanner failed; verify installation, platform and checksum.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
