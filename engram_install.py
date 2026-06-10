"""Multi-client MCP + skill installer — detects Claude Code, Cursor, Windsurf, and Antigravity."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ENGRAM_DIR = Path(__file__).parent.resolve()
MCP_SERVER = ENGRAM_DIR / "engram_mcp_server.py"
SKILL_SRC = ENGRAM_DIR / "skill"   # the skill/ directory inside this repo


def _python() -> str:
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
