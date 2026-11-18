"""Diagnostic: test asyncio subprocess on Windows."""
import asyncio
import subprocess
import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent

async def test():
    print(f"Python: {sys.executable}")
    print(f"Platform: {sys.platform}")
    print(f"Event loop policy: {asyncio.get_event_loop_policy().__class__.__name__}")
    print(f"CWD: {PROJECT_ROOT}")

    payload = json.dumps({"requirement": "Build a hello world API", "project_id": "p1"}).encode()

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "nodes/planner.py",
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(PROJECT_ROOT)
        )
        out, err = await proc.communicate(payload)
        print(f"Return code: {proc.returncode}")
        print(f"STDOUT: {out.decode()[:500]}")
        print(f"STDERR: {err.decode()[:500]}")
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {e}")

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

asyncio.run(test())
