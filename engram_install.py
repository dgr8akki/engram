"""Multi-client MCP installer — detects Claude Code, Cursor, Windsurf, and Antigravity."""

import json
import shutil
import subprocess
import sys
from pathlib import Path


ENGRAM_DIR = Path(__file__).parent.resolve()
MCP_SERVER = ENGRAM_DIR / "engram_mcp_server.py"


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
