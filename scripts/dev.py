#!/usr/bin/env python3
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(cmd, cwd=None):
    print(f">>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd or ROOT, check=True)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "help"

    if target == "dev":
        api_env = os.environ.copy()
        api_proc = subprocess.Popen(
            [str(ROOT / "apps/api/.venv/bin/uvicorn"), "app.main:app", "--reload", "--port", "8000"],
            cwd=ROOT / "apps/api",
            env=api_env,
        )
        web_proc = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd=ROOT / "apps/web",
        )
        try:
            api_proc.wait()
        except KeyboardInterrupt:
            api_proc.terminate()
            web_proc.terminate()
    elif target == "seed":
        run([str(ROOT / "apps/api/.venv/bin/python"), "scripts/seed.py"], cwd=ROOT / "apps/api")
    elif target == "test-api":
        run([str(ROOT / "apps/api/.venv/bin/pytest"), "tests", "-v"], cwd=ROOT / "apps/api")
    elif target == "test-contracts":
        run(["forge", "test", "-vv"], cwd=ROOT / "contracts")
    elif target == "test":
        run([str(ROOT / "apps/api/.venv/bin/pytest"), "tests", "-v"], cwd=ROOT / "apps/api")
        if (ROOT / "contracts/lib").exists() or shutil_which("forge"):
            try:
                run(["forge", "test", "-vv"], cwd=ROOT / "contracts")
            except Exception:
                print("Skipping contract tests (forge/OpenZeppelin not installed)")
    elif target == "install":
        run(["python3", "-m", "venv", ".venv"], cwd=ROOT / "apps/api")
        run([str(ROOT / "apps/api/.venv/bin/pip"), "install", "-r", "requirements.txt"], cwd=ROOT / "apps/api")
        run(["npm", "install"], cwd=ROOT / "apps/web")
    else:
        print("Usage: make dev | seed | test | test-api | test-contracts | install")


def shutil_which(cmd):
    from shutil import which
    return which(cmd)


if __name__ == "__main__":
    main()
