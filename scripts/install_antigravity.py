"""Install this checkout for the current Windows user. No administrator rights required."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import venv


UPSTREAM_MAIN_SHA256 = "cba5f410293941f934004ac9078e9ae64af997de74bfec441e8ea5a632ac121d"


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(data)
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def install():
    if os.name != "nt" or sys.version_info < (3, 10):
        raise SystemExit("Use Windows and Python 3.10 or newer.")
    repo = Path(__file__).resolve().parents[1]
    base = Path(os.environ["LOCALAPPDATA"]) / "AntigravityTools/mhyrr-sketchup-mcp"
    env_dir = base / "venv"
    python = env_dir / "Scripts/python.exe"
    server = env_dir / "Scripts/sketchup-mcp.exe"
    config = Path.home() / ".gemini/config/mcp_config.json"
    original = config.read_bytes() if config.exists() else b"{}"
    settings = json.loads(original.decode("utf-8-sig"))
    servers = settings.setdefault("mcpServers", {})
    entry = {"command": str(server), "args": []}
    previous = {"command": str(python), "args": ["-u", str(base / "mhyrr_launcher.py")]}
    if "sketchup-mhyrr" in servers and servers["sketchup-mhyrr"] not in (entry, previous):
        raise SystemExit("The server name sketchup-mhyrr already has different settings.")
    roots = []
    for profile in (Path(os.environ["APPDATA"]) / "SketchUp").glob("SketchUp *"):
        installed = Path(os.environ["ProgramFiles"]) / "SketchUp" / profile.name / "SketchUp/SketchUp.exe"
        if installed.is_file() and (profile / "SketchUp").is_dir():
            roots.append(profile / "SketchUp/Plugins")
    if not roots:
        raise SystemExit("Open the installed desktop version of SketchUp once and run this command again.")
    updates = {}
    for root in roots:
        for name in ("su_mcp.rb", "su_mcp/main.rb"):
            target = root / name
            data = (repo / "su_mcp" / name).read_bytes()
            if target.exists():
                existing = target.read_bytes().replace(b"\r\n", b"\n")
                if existing == data.replace(b"\r\n", b"\n"):
                    continue
                if name != "su_mcp/main.rb" or hashlib.sha256(existing).hexdigest() != UPSTREAM_MAIN_SHA256:
                    raise SystemExit(f"Another extension occupies {target}. Resolve the conflict and rerun.")
            updates[target] = data
    uv = shutil.which("uv")
    if not python.exists():
        if uv:
            subprocess.run([uv, "venv", "--python", sys.executable, str(env_dir)], check=True)
        else:
            venv.EnvBuilder(with_pip=True).create(env_dir)
    if uv:
        # Rebuild the local package even if another checkout used the same version.
        subprocess.run([uv, "pip", "install", "--python", str(python),
                        "--reinstall-package", "sketchup-mcp", str(repo)], check=True)
    else:
        subprocess.run([str(python), "-m", "pip", "install", str(repo)], check=True)
    if not server.is_file():
        raise SystemExit("The MCP executable is missing after installation.")
    for target, data in updates.items():
        atomic_write(target, data)
    servers["sketchup-mhyrr"] = entry
    if (config.read_bytes() if config.exists() else b"{}") != original:
        raise SystemExit("The Antigravity configuration changed. Run the installer again.")
    atomic_write(config, (json.dumps(settings, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print("Installed sketchup-mhyrr for " + ", ".join(root.parents[1].name for root in roots))
    print("Restart SketchUp, then choose Extensions > MCP Server > Start Server in the model window.")


if __name__ == "__main__":
    install()
