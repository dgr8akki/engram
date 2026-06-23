"""Multi-client MCP + skill installer — detects Claude Code, Cursor, Windsurf, and Antigravity."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ENGRAM_DIR = Path(__file__).parent.resolve()

def _libexec() -> Path:
    """Stable libexec path — prefers Homebrew opt over versioned Cellar."""
    for opt in [
        Path("/opt/homebrew/opt/engram/libexec"),
        Path("/usr/local/opt/engram/libexec"),
    ]:
        if opt.exists():
            return opt
    return ENGRAM_DIR

_BASE = _libexec()
MCP_SERVER   = _BASE / "engram_mcp_server.py"
SKILL_SRC    = _BASE / "skill"
SCRIPTS_DIR_ = _BASE / "scripts"  # renamed; SCRIPTS_DIR set below after hook helpers


def _python() -> str:
    py = _BASE / "venv" / "bin" / "python3"
    if py.exists():
        return str(py)
    # Dev / non-Homebrew install
    venv = ENGRAM_DIR / "venv" / "bin" / "python3"
    if venv.exists():
        return str(venv)
    return sys.executable


def _mcp_server_entry() -> dict:
    return {
        "command": _python(),
        "args": [str(MCP_SERVER)]
    }


def _write_json_mcp_config(config_file: Path, server_name: str = "engram"):
    config_file.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if config_file.exists():
        try:
            existing = json.loads(config_file.read_text())
        except json.JSONDecodeError:
            pass

    servers = existing.setdefault("mcpServers", {})
    servers[server_name] = _mcp_server_entry()
    config_file.write_text(json.dumps(existing, indent=2) + "\n")
    return config_file


def install_claude_code() -> bool:
    if not shutil.which("claude"):
        return False
    try:
        result = subprocess.run(
            [
                "claude", "mcp", "add",
                "--scope", "user",
                "--transport", "stdio",
                "engram", "--",
                _python(), str(MCP_SERVER)
            ],
            capture_output=True, text=True
        )
        return result.returncode == 0
    except Exception:
        return False


def install_cursor() -> bool:
    config_file = Path.home() / ".cursor" / "mcp.json"
    if not (Path.home() / ".cursor").exists():
        return False
    _write_json_mcp_config(config_file)
    return True


def install_windsurf() -> bool:
    config_file = Path.home() / ".windsurf" / "mcp.json"
    if not (Path.home() / ".windsurf").exists():
        return False
    _write_json_mcp_config(config_file)
    return True


def install_antigravity() -> bool:
    # Antigravity reads from ~/.gemini/config/mcp_config.json
    config_dir = Path.home() / ".gemini" / "config"
    if not config_dir.parent.exists() and not shutil.which("antigravity"):
        return False
    _write_json_mcp_config(config_dir / "mcp_config.json")
    return True


def install_cline() -> bool:
    # Cline (VS Code extension) reads from ~/.cline/mcp_settings.json
    config_file = Path.home() / ".cline" / "mcp_settings.json"
    if not (Path.home() / ".cline").exists():
        return False
    _write_json_mcp_config(config_file)
    return True


CLIENTS = {
    "Claude Code": install_claude_code,
    "Cursor": install_cursor,
    "Windsurf": install_windsurf,
    "Antigravity": install_antigravity,
    "Cline": install_cline,
}


def run_install(verbose: bool = False):
    print("Engram installer — detecting AI coding tools...\n")
    installed_any = False

    for name, fn in CLIENTS.items():
        try:
            ok = fn()
            if ok:
                print(f"  [OK] {name}")
                installed_any = True
            elif verbose:
                print(f"  [--] {name} (not detected)")
        except Exception as e:
            if verbose:
                print(f"  [!!] {name}: {e}")

    if not installed_any:
        print("\nNo supported AI coding tools detected.")
        print("Install one of: Claude Code, Cursor, Windsurf, Antigravity, Cline")
        print("\nOr register manually — MCP server path:")
        print(f"  {_python()} {MCP_SERVER}")
        return

    print(f"\nRestart your IDE/tool to load the 'engram' MCP server.")
    print(f"Server: {_python()} {MCP_SERVER}")

    print()
    run_skill_install(verbose=verbose)

    print()
    run_hooks_install(verbose=verbose)


# ---------------------------------------------------------------------------
# Skill installer
# ---------------------------------------------------------------------------

def _symlink(src: Path, dest: Path) -> bool:
    """Create or update a symlink at dest pointing to src. Returns True on success."""
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink() or dest.exists():
            dest.unlink()
        os.symlink(src, dest)
        return True
    except Exception:
        return False


def install_skill_claude_code() -> bool:
    """~/.claude/skills/engram -> ~/.agents/skills/engram"""
    dest = Path.home() / ".claude" / "skills" / "engram"
    canonical = Path.home() / ".agents" / "skills" / "engram"
    if not (Path.home() / ".claude").exists():
        return False
    return _symlink(canonical, dest)


def install_skill_antigravity() -> bool:
    """~/.gemini/antigravity/skills/engram -> ~/.agents/skills/engram"""
    skills_dir = Path.home() / ".gemini" / "antigravity" / "skills"
    if not skills_dir.parent.exists():
        return False
    canonical = Path.home() / ".agents" / "skills" / "engram"
    return _symlink(canonical, skills_dir / "engram")


def install_skill_antigravity_ide() -> bool:
    """~/.gemini/antigravity-ide/skills/engram -> ~/.agents/skills/engram (if dir exists)"""
    skills_dir = Path.home() / ".gemini" / "antigravity-ide" / "skills"
    if not skills_dir.parent.exists():
        return False
    canonical = Path.home() / ".agents" / "skills" / "engram"
    return _symlink(canonical, skills_dir / "engram")


def install_skill_cursor() -> bool:
    """~/.cursor/skills/engram -> ~/.agents/skills/engram (if ~/.cursor exists)"""
    if not (Path.home() / ".cursor").exists():
        return False
    canonical = Path.home() / ".agents" / "skills" / "engram"
    return _symlink(canonical, Path.home() / ".cursor" / "skills" / "engram")


def install_skill_windsurf() -> bool:
    """~/.windsurf/skills/engram -> ~/.agents/skills/engram (if ~/.windsurf exists)"""
    if not (Path.home() / ".windsurf").exists():
        return False
    canonical = Path.home() / ".agents" / "skills" / "engram"
    return _symlink(canonical, Path.home() / ".windsurf" / "skills" / "engram")


SKILL_CLIENTS = {
    "Claude Code": install_skill_claude_code,
    "Antigravity": install_skill_antigravity,
    "Antigravity IDE": install_skill_antigravity_ide,
    "Cursor": install_skill_cursor,
    "Windsurf": install_skill_windsurf,
}


def run_skill_install(verbose: bool = False):
    canonical = Path.home() / ".agents" / "skills" / "engram"

    # Step 1: canonical location — symlink ~/.agents/skills/engram -> repo/skill/
    print("Installing Engram skill...\n")
    if not SKILL_SRC.exists():
        print(f"  [!!] skill/ directory not found at {SKILL_SRC}")
        return

    canonical.parent.mkdir(parents=True, exist_ok=True)
    if canonical.is_symlink() or canonical.exists():
        canonical.unlink() if canonical.is_symlink() else shutil.rmtree(canonical)
    os.symlink(SKILL_SRC, canonical)
    print(f"  [OK] ~/.agents/skills/engram -> {SKILL_SRC}")

    # Step 2: tool-specific symlinks -> canonical
    installed_any = False
    for name, fn in SKILL_CLIENTS.items():
        try:
            ok = fn()
            if ok:
                print(f"  [OK] {name}")
                installed_any = True
            elif verbose:
                print(f"  [--] {name} (not detected)")
        except Exception as e:
            if verbose:
                print(f"  [!!] {name}: {e}")

    if not installed_any:
        print("\n  No supported tool skill directories detected.")
        print("  The skill is at ~/.agents/skills/engram — link it manually if needed.")
    else:
        print("\nSkill installed. Restart your IDE/tool to activate it.")
        print(f"Skill source: {SKILL_SRC / 'SKILL.md'}")


# ---------------------------------------------------------------------------
# Hook installer
# ---------------------------------------------------------------------------

SCRIPTS_DIR = SCRIPTS_DIR_


def _hook_cmd(script: str) -> str:
    return f"{_python()} {SCRIPTS_DIR / script}"


def _merge_hooks(settings: dict, new_hooks: dict) -> dict:
    """Merge new_hooks into settings['hooks'] without overwriting unrelated entries."""
    existing = settings.setdefault("hooks", {})
    for event, entries in new_hooks.items():
        bucket = existing.setdefault(event, [])
        # Remove any previous engram hook entry for this event
        bucket[:] = [
            e for e in bucket
            if not any("engram_" in str(h.get("command", "")) for h in e.get("hooks", [e]))
        ]
        bucket.extend(entries)
    return settings


def _read_json(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def install_hooks_claude_code() -> bool:
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.parent.exists():
        return False

    settings = _read_json(settings_path)
    new_hooks = {
        "SessionStart": [{"hooks": [{"type": "command", "command": _hook_cmd("engram_session_start.py"), "timeout": 10}]}],
        "UserPromptSubmit": [{"hooks": [{"type": "command", "command": _hook_cmd("engram_user_prompt.py"), "timeout": 30}]}],
        "Stop": [{"hooks": [{"type": "command", "command": _hook_cmd("engram_session_end.py"), "timeout": 60}]}],
    }
    _merge_hooks(settings, new_hooks)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    return True


def install_hooks_antigravity_cli() -> bool:
    # Antigravity CLI reads from ~/.gemini/settings.json
    settings_path = Path.home() / ".gemini" / "settings.json"
    gemini_dir = Path.home() / ".gemini"
    if not gemini_dir.exists():
        return False

    settings = _read_json(settings_path)
    new_hooks = {
        "SessionStart": [{"hooks": [{"type": "command", "command": _hook_cmd("engram_session_start.py"), "timeout": 10000}]}],
        "BeforeAgent": [{"hooks": [{"type": "command", "command": _hook_cmd("engram_user_prompt.py"), "timeout": 30000}]}],
        "SessionEnd": [{"hooks": [{"type": "command", "command": _hook_cmd("engram_session_end.py")}]}],
    }
    _merge_hooks(settings, new_hooks)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    return True


def install_hooks_cursor() -> bool:
    hooks_path = Path.home() / ".cursor" / "hooks.json"
    if not (Path.home() / ".cursor").exists():
        return False

    settings = _read_json(hooks_path)
    settings.setdefault("version", 1)
    hooks = settings.setdefault("hooks", {})

    # Map event → ordered list of scripts to install
    event_scripts = {
        "sessionStart":       ["engram_session_start.py", "engram_rules_update.py"],
        "beforeSubmitPrompt": ["engram_user_prompt.py"],
        "sessionEnd":         ["engram_session_end.py"],
    }
    for event, scripts in event_scripts.items():
        bucket = hooks.setdefault(event, [])
        bucket[:] = [e for e in bucket if "engram_" not in e.get("command", "")]
        bucket.extend({"command": _hook_cmd(s)} for s in scripts)

    hooks_path.write_text(json.dumps(settings, indent=2) + "\n")
    return True


def install_hooks_windsurf() -> bool:
    # Windsurf: write to ~/.codeium/windsurf/hooks.json
    hooks_dir = Path.home() / ".codeium" / "windsurf"
    if not hooks_dir.parent.exists():
        return False

    hooks_dir.mkdir(parents=True, exist_ok=True)
    hooks_path = hooks_dir / "hooks.json"
    settings = _read_json(hooks_path)
    hooks = settings.setdefault("hooks", {})

    for event, script in [
        ("pre_user_prompt", "engram_rules_update.py"),
        ("post_cascade_response_with_transcript", "engram_session_end.py"),
    ]:
        bucket = hooks.setdefault(event, [])
        bucket[:] = [e for e in bucket if "engram_" not in e.get("command", "")]
        bucket.append({"command": _hook_cmd(script), "show_output": False})

    hooks_path.write_text(json.dumps(settings, indent=2) + "\n")
    return True


HOOK_CLIENTS = {
    "Claude Code": install_hooks_claude_code,
    "Antigravity CLI": install_hooks_antigravity_cli,
    "Cursor": install_hooks_cursor,
    "Windsurf": install_hooks_windsurf,
}


def run_hooks_install(verbose: bool = False):
    print("Installing memory hooks...\n")
    installed_any = False

    for name, fn in HOOK_CLIENTS.items():
        try:
            ok = fn()
            if ok:
                print(f"  [OK] {name}")
                installed_any = True
            elif verbose:
                print(f"  [--] {name} (not detected)")
        except Exception as e:
            if verbose:
                print(f"  [!!] {name}: {e}")

    if not installed_any:
        print("  No supported tools detected for hook installation.")
    else:
        print("\nHooks installed:")
        print("  Session start  → injects recent memories as context")
        print("  User prompt    → auto-saves when you say 'remember: ...'")
        print("  Session end    → records session topic to Engram")


# ---------------------------------------------------------------------------
# LaunchAgent (macOS autostart)
# ---------------------------------------------------------------------------

LAUNCH_AGENT_LABEL = "com.engram.server"
LAUNCH_AGENT_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def _plist_content() -> str:
    python = _python()
    cli = str(_BASE / "engram_cli.py")
    log = str(Path.home() / "Library" / "Logs" / "engram.log")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{cli}</string>
        <string>serve</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
</dict>
</plist>
"""


def install_launch_agent() -> tuple[bool, str]:
    """Install and load the Engram HTTP server as a macOS LaunchAgent."""
    import platform
    if platform.system() != "Darwin":
        return False, "LaunchAgents are macOS-only"

    LAUNCH_AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENT_PLIST.write_text(_plist_content())

    # Unload first in case it was already loaded with a stale plist
    subprocess.run(
        ["launchctl", "unload", str(LAUNCH_AGENT_PLIST)],
        capture_output=True,
    )
    result = subprocess.run(
        ["launchctl", "load", str(LAUNCH_AGENT_PLIST)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "launchctl load failed"
    return True, str(LAUNCH_AGENT_PLIST)


def remove_launch_agent() -> tuple[bool, str]:
    """Unload and remove the Engram LaunchAgent."""
    if not LAUNCH_AGENT_PLIST.exists():
        return False, f"plist not found: {LAUNCH_AGENT_PLIST}"

    subprocess.run(
        ["launchctl", "unload", str(LAUNCH_AGENT_PLIST)],
        capture_output=True,
    )
    LAUNCH_AGENT_PLIST.unlink()
    return True, str(LAUNCH_AGENT_PLIST)


# ---------------------------------------------------------------------------
# Rules updater LaunchAgent (keeps global rules files current for hookless tools)
# ---------------------------------------------------------------------------

RULES_AGENT_LABEL = "com.engram.rules"
RULES_AGENT_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{RULES_AGENT_LABEL}.plist"


def _rules_plist_content() -> str:
    python = _python()
    cli    = str(_BASE / "engram_cli.py")
    log    = str(Path.home() / "Library" / "Logs" / "engram.log")
    home   = str(Path.home())
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{RULES_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{cli}</string>
        <string>rules</string>
        <string>update</string>
        <string>--dir</string>
        <string>{home}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>1800</integer>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
</dict>
</plist>
"""


def install_rules_agent() -> tuple[bool, str]:
    """Install the rules-updater LaunchAgent (macOS only)."""
    import platform
    if platform.system() != "Darwin":
        return False, "LaunchAgents are macOS-only"

    RULES_AGENT_PLIST.parent.mkdir(parents=True, exist_ok=True)
    RULES_AGENT_PLIST.write_text(_rules_plist_content())

    subprocess.run(["launchctl", "unload", str(RULES_AGENT_PLIST)], capture_output=True)
    result = subprocess.run(
        ["launchctl", "load", str(RULES_AGENT_PLIST)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip() or "launchctl load failed"

    msg = (
        f"Plist: {RULES_AGENT_PLIST}\n"
        f"Updates: ~/.cursorrules, ~/.windsurfrules, ~/.github/copilot-instructions.md"
    )
    return True, msg


def launch_agent_status() -> str:
    """Return human-readable status of the Engram LaunchAgent."""
    if not LAUNCH_AGENT_PLIST.exists():
        return "not installed"

    result = subprocess.run(
        ["launchctl", "list", LAUNCH_AGENT_LABEL],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return "installed (not loaded)"

    # Parse PID from launchctl list output (first column)
    first_line = result.stdout.strip().splitlines()[1] if "\n" in result.stdout else ""
    pid = first_line.split()[0] if first_line else "-"
    return f"running (pid {pid})" if pid != "-" else "loaded (idle)"
