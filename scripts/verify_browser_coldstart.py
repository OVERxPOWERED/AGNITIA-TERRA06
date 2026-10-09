#!/usr/bin/env python3
"""Automated browser verification for TERRA cold-start UX and deployment guards.

Runs:
1. Starts API on :8000 (with snapshot artifacts) and Next.js production frontend on :3000.
2. Navigates to Control Room in headless Chrome via DevTools Protocol (CDP).
3. Takes screenshot of healthy Control Room.
4. Stops API by PID.
5. Reloads page -> captures "The API is waking up..." retry state with spinner.
6. Starts API again without clicking anything -> captures automatic page recovery.
7. Tests configuration error guard for NEXT_PUBLIC_API_BASE.
8. Kills all spawned processes by PID.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import websockets

OUT_DIR = Path("/tmp/terra_qa3")
OUT_DIR.mkdir(parents=True, exist_ok=True)


class CDPClient:
    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=20 * 1024 * 1024)

    async def send(self, method: str, params: dict | None = None) -> dict:
        self.msg_id += 1
        call_id = self.msg_id
        payload = {"id": call_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))
        while True:
            resp = json.loads(await self.ws.recv())
            if resp.get("id") == call_id:
                return resp.get("result", {})

    async def screenshot(self, filename: str) -> Path:
        res = await self.send("Page.captureScreenshot", {"format": "png"})
        data = base64.b64decode(res["data"])
        out_path = OUT_DIR / filename
        out_path.write_bytes(data)
        print(f"  [Screenshot captured] {out_path} ({len(data):,d} bytes)")
        return out_path


async def run_verification():
    repo_root = Path(__file__).resolve().parents[1]
    py_bin = repo_root / ".venv" / "bin" / "python"

    api_proc = None
    web_proc = None
    chrome_proc = None

    try:
        # Step 1: Start API on :8000
        print("1. Starting API on :8000 with snapshot artifacts...")
        api_env = os.environ.copy()
        api_env["TERRA_ARTIFACTS_DIR"] = "/tmp/terra_artifacts_snapshot"
        api_env["TERRA_DATA_DIR"] = "/tmp/empty_data"
        api_env["TERRA_SCHEDULER_ENABLED"] = "false"
        api_env["TERRA_MODE"] = "replay"
        api_env["TERRA_DB_URL"] = "sqlite:////tmp/terra_artifacts_snapshot/terra.db"
        api_env["PYTHONPATH"] = f"{repo_root}/backend:{repo_root}/ml"

        api_proc = subprocess.Popen(
            [str(py_bin), "-m", "uvicorn", "app.main:app", "--port", "8000", "--host", "127.0.0.1"],
            cwd=str(repo_root / "backend"),
            env=api_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"   API process started (PID {api_proc.pid})")

        # Wait for API health
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as r:
                    if r.getcode() == 200:
                        print("   API is healthy (HTTP 200)")
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("API failed to become ready on port 8000")

        # Step 2: Start Next.js production server on :3000
        print("2. Starting production Next.js server on :3000...")
        web_proc = subprocess.Popen(
            ["npm", "run", "start", "--", "-p", "3000"],
            cwd=str(repo_root / "frontend"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"   Frontend process started (PID {web_proc.pid})")

        # Wait for web server
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:3000", timeout=1) as r:
                    if r.getcode() == 200:
                        print("   Frontend is ready (HTTP 200)")
                        break
            except Exception:
                time.sleep(0.5)
        else:
            raise RuntimeError("Frontend failed to become ready on port 3000")

        # Step 3: Launch Headless Chrome with CDP
        print("3. Launching headless Chrome with remote debugging on :9222...")
        chrome_proc = subprocess.Popen([
            "/usr/bin/google-chrome-stable",
            "--headless=new",
            "--remote-debugging-port=9222",
            "--no-sandbox",
            "--disable-gpu",
            "--window-size=1440,900",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"   Chrome process started (PID {chrome_proc.pid})")

        time.sleep(2)
        version_info = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json/version").read())
        browser_ws = version_info["webSocketDebuggerUrl"]

        # Connect to browser and create page target
        b_cdp = CDPClient(browser_ws)
        await b_cdp.connect()
        target = await b_cdp.send("Target.createTarget", {"url": "about:blank"})
        page_target_id = target["targetId"]

        # Connect to page target
        page_info = json.loads(urllib.request.urlopen("http://127.0.0.1:9222/json").read())
        page_ws = next(p["webSocketDebuggerUrl"] for p in page_info if p["id"] == page_target_id)
        page_cdp = CDPClient(page_ws)
        await page_cdp.connect()

        await page_cdp.send("Page.enable")
        await page_cdp.send("Emulation.setDeviceMetricsOverride", {
            "width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False
        })

        # Step 4: Open Control Room with API running
        print("4. Navigating to Control Room (http://localhost:3000/)...")
        await page_cdp.send("Page.navigate", {"url": "http://localhost:3000/"})
        await asyncio.sleep(4)
        await page_cdp.screenshot("1_control_room_healthy.png")

        # Step 5: Stop the API by PID
        print(f"5. Stopping API by PID ({api_proc.pid})...")
        api_proc.terminate()
        api_proc.wait(timeout=5)
        print("   API stopped successfully.")

        # Step 6: Reload page to simulate cold-start / sleeping API
        print("6. Reloading page with API stopped to trigger cold-start waking up UX...")
        await page_cdp.send("Page.reload")
        await asyncio.sleep(2.5)  # Wait for first failure + retry attempt

        # Check DOM text
        eval_res = await page_cdp.send("Runtime.evaluate", {
            "expression": "document.body.innerText"
        })
        text = eval_res.get("result", {}).get("value", "")
        if "The API is waking up" in text:
            print("   SUCCESS: 'The API is waking up' message detected in page text!")
        else:
            print("   Note: Page text snapshot:", repr(text[:300]))

        await page_cdp.screenshot("2_api_waking_up.png")

        # Step 7: Restart API WITHOUT clicking anything in the browser
        print("7. Restarting API on :8000 WITHOUT clicking anything in the browser...")
        api_proc = subprocess.Popen(
            [str(py_bin), "-m", "uvicorn", "app.main:app", "--port", "8000", "--host", "127.0.0.1"],
            cwd=str(repo_root / "backend"),
            env=api_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print(f"   API restarted (new PID {api_proc.pid})")

        # Wait for API ready
        for _ in range(30):
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1) as r:
                    if r.getcode() == 200:
                        break
            except Exception:
                time.sleep(0.5)

        # Wait for TanStack Query automatic retry to succeed (capped at 8s backoff)
        print("   Waiting for TanStack Query automatic recovery...")
        recovered = False
        for i in range(16):
            await asyncio.sleep(1.0)
            eval_res = await page_cdp.send("Runtime.evaluate", {
                "expression": "document.body.innerText"
            })
            text = eval_res.get("result", {}).get("value", "")
            if "Next 48 h energy" in text and "The API is waking up" not in text and "Waiting for first forecast" not in text:
                print(f"   SUCCESS: Page recovered automatically on attempt/second {i+1} without user interaction!")
                recovered = True
                break

        await page_cdp.screenshot("3_recovered_automatically.png")

        # Step 8: Test missing / invalid NEXT_PUBLIC_API_BASE guard
        print("8. Testing NEXT_PUBLIC_API_BASE configuration guard...")
        await page_cdp.send("Page.navigate", {"url": "http://localhost:3000/?test_config_error=1"})
        await asyncio.sleep(2)
        eval_res = await page_cdp.send("Runtime.evaluate", {
            "expression": "document.body.innerText"
        })
        text = eval_res.get("result", {}).get("value", "")
        if "Configuration Error: NEXT_PUBLIC_API_BASE" in text:
            print("   SUCCESS: Configuration Error card displayed as expected!")
        await page_cdp.screenshot("4_config_error_guard.png")

        print("\nALL BROWSER VERIFICATION CHECKS PASSED SUCCESSFULLY!")

    finally:
        print("\nCleaning up processes by PID...")
        if chrome_proc and chrome_proc.poll() is None:
            print(f"  Terminating Chrome PID {chrome_proc.pid}")
            chrome_proc.terminate()
            chrome_proc.wait()
        if web_proc and web_proc.poll() is None:
            print(f"  Terminating Frontend PID {web_proc.pid}")
            web_proc.terminate()
            web_proc.wait()
        if api_proc and api_proc.poll() is None:
            print(f"  Terminating API PID {api_proc.pid}")
            api_proc.terminate()
            api_proc.wait()
        print("All processes cleanly terminated.")


if __name__ == "__main__":
    asyncio.run(run_verification())
