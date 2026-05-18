"""
RPG-AI-FRAMEWORK launcher.
Double-click RPG.bat (Windows) or run: python launch.py
Starts the server and opens the game in your browser automatically.
"""

import os
import sys
import subprocess
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).parent


def check_env() -> bool:
    env_file = ROOT / ".env"
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key or key.startswith("sk-ant-YOUR"):
        print("=" * 60)
        print("  SETUP REQUIRED")
        print("=" * 60)
        print()
        print("  No API key found. Create a .env file in this folder:")
        print()
        print("    ANTHROPIC_API_KEY=sk-ant-...")
        print()
        print("  Get your key at: console.anthropic.com")
        print()
        if sys.platform == "win32":
            input("  Press Enter to exit...")
        return False
    return True


def main():
    os.chdir(ROOT)

    if not check_env():
        sys.exit(1)

    # Start uvicorn, hidden on Windows
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--port", "8000"],
        **kwargs,
    )

    print("Starting server", end="", flush=True)
    for _ in range(12):
        time.sleep(0.5)
        print(".", end="", flush=True)
        try:
            import httpx
            httpx.get("http://localhost:8000/health", timeout=1)
            break
        except Exception:
            pass
    print()

    print("Opening browser...")
    webbrowser.open("http://localhost:8000")

    print("Game running at http://localhost:8000")
    print("Press Ctrl+C to stop.")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\nShutting down...")
        proc.terminate()


if __name__ == "__main__":
    main()
