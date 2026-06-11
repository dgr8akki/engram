"""Multi-client MCP + skill installer — detects Claude Code, Cursor, Windsurf, and Antigravity."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ENGRAM_DIR = Path(__file__).parent.resolve()
MCP_SERVER = ENGRAM_DIR / "engram_mcp_server.py"

def _skill_src() -> Path:
    """Return the stable skill path.

    When installed via Homebrew the versioned Cellar path changes on every
    upgrade, breaking symlinks. Homebrew keeps a stable opt symlink at
    /opt/homebrew/opt/engram (Apple Silicon) or /usr/local/opt/engram (Intel)
    that always points to the current version — use that instead.
    """
    for opt in [
        Path("/opt/homebrew/opt/engram/libexec/skill"),
        Path("/usr/local/opt/engram/libexec/skill"),
    ]:
        if opt.exists():
            return opt
    return ENGRAM_DIR / "skill"

SKILL_SRC = _skill_src()


def _python() -> str:
    # Homebrew opt path is stable across upgrades
    for opt_py in [
        Path("/opt/homebrew/opt/engram/libexec/venv/bin/python3"),
        Path("/usr/local/opt/engram/libexec/venv/bin/python3"),
    ]:
        if opt_py.exists():
            return str(opt_py)
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

def _scripts_dir() -> Path:
    """Stable scripts path — prefers Homebrew opt over versioned Cellar."""
    for opt in [
        Path("/opt/homebrew/opt/engram/libexec/scripts"),
        Path("/usr/local/opt/engram/libexec/scripts"),
    ]:
        if opt.exists():
            return opt
    return ENGRAM_DIR / "scripts"

SCRIPTS_DIR = _scripts_dir()


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

    for event, script in [
        ("sessionStart", "engram_session_start.py"),
        ("beforeSubmitPrompt", "engram_user_prompt.py"),
        ("sessionEnd", "engram_session_end.py"),
    ]:
        bucket = hooks.setdefault(event, [])
        bucket[:] = [e for e in bucket if "engram_" not in e.get("command", "")]
        bucket.append({"command": _hook_cmd(script)})

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
        ("pre_user_prompt", "engram_windsurf_update.py"),
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
