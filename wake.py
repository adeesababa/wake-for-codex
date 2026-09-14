#!/usr/bin/env python3
"""Wake: resume a Codex task after a verified usage reset. Python standard library only."""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time

VERSION = "0.1.0"
CONTINUE = ("Continue the unfinished task from the last usage-limit interruption. "
            "Inspect the existing work before making changes. Follow the original scope "
            "and permissions. If the task is already complete, stop and report that.")


class WakeError(Exception):
    pass


def usage_failure(turn):
    return (turn.get("status") == "failed" and
            (turn.get("error") or {}).get("codexErrorInfo") == "usageLimitExceeded")


def quota_state(response, bucket="codex"):
    """Unknown is never interpreted as available; check both quota windows."""
    buckets = response.get("rateLimitsByLimitId")
    if buckets is not None:
        selected = buckets.get(bucket)
    else:
        selected = response.get("rateLimits")
        if selected and selected.get("limitId") not in (None, bucket):
            selected = None
    if not isinstance(selected, dict):
        return "unknown", None
    windows = [selected[k] for k in ("primary", "secondary") if selected.get(k) is not None]
    if not windows:
        return "unknown", None
    for window in windows:
        value = window.get("usedPercent")
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value < 0:
            return "unknown", None
    blocked = [w for w in windows if w["usedPercent"] >= 100]
    if blocked:
        resets = [w.get("resetsAt") for w in blocked]
        reset = max(resets) if all(isinstance(r, (int, float)) and math.isfinite(r) for r in resets) else None
        return "blocked", reset
    if selected.get("rateLimitReachedType"):
        return "unknown", None
    return "available", None


class Client:
    """Line-delimited app-server RPC, bounded requests, no credential handling."""
    def __init__(self, executable="codex"):
        exe = shutil.which(executable)
        if not exe:
            raise WakeError("Codex was not found. Install Codex CLI, then run codex login.")
        self.proc = subprocess.Popen([exe, "app-server"], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=None, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self.messages = queue.Queue()
        self.pending = {}
        self.events = queue.Queue()
        self.counter = 0
        self.needs_attention = False
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call("initialize", {"clientInfo": {"name": "wake", "title": "Wake", "version": VERSION}})
            self.send({"method": "initialized"})
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            for line in self.proc.stdout:
                try:
                    self.messages.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
        finally:
            self.messages.put(None)

    def send(self, message):
        self.proc.stdin.write(json.dumps(message) + "\n")
        self.proc.stdin.flush()

    def receive(self, timeout):
        try:
            msg = self.messages.get(timeout=timeout)
        except queue.Empty:
            return
        if msg is None:
            raise WakeError("Codex disconnected. Restart Wake after checking codex login.")
        if "method" in msg and "id" in msg:
            # Do not silently approve commands, file changes, or user-input requests.
            self.needs_attention = True
            self.send({"id": msg["id"], "error": {"code": -32601,
                "message": "Wake cannot approve or answer this request. Open the task in Codex."}})
        elif "id" in msg:
            self.pending[msg["id"]] = msg
        else:
            self.events.put(msg)

    def call(self, method, params=None, timeout=60):
        self.counter += 1
        request_id = self.counter
        self.send({"id": request_id, "method": method, "params": params or {}})
        deadline = time.monotonic() + timeout
        while request_id not in self.pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WakeError(f"{method} timed out; no automatic retry of an uncertain request.")
            self.receive(min(remaining, 1))
        result = self.pending.pop(request_id)
        if "error" in result:
            raise WakeError(f"{method}: {result['error'].get('message', 'request failed')}")
        return result["result"]

    def close(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        for stream in (self.proc.stdin, self.proc.stdout):
            stream.close()


class Journal:
    """Persist a claim before sending; uncertain dispatches require manual recovery."""
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / "state.json"
        self.lock = self.folder / "watch.lock"
        try:
            self.handle = self.lock.open("x")
        except FileExistsError:
            raise WakeError(f"Another watcher or stale lock exists: {self.lock}. See README recovery steps.")
        self.handle.write(str(os.getpid()))
        self.handle.flush()
        try:
            self.data = json.loads(self.path.read_text()) if self.path.exists() else {"claims": {}}
        except BaseException:
            self.close()
            raise

    def claim(self, thread_id, turn_id):
        key = thread_id + ":" + turn_id
        if key in self.data["claims"]:
            raise WakeError("This interrupted turn was already claimed. Inspect the task before manual recovery.")
        self.data["claims"][key] = {"at": time.time(), "status": "dispatching"}
        temp = self.path.with_suffix(".tmp")
        with temp.open("w") as out:
            json.dump(self.data, out, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, self.path)

    def close(self):
        self.handle.close()
        self.lock.unlink(missing_ok=True)


def read_task(client, thread_id):
    thread = client.call("thread/read", {"threadId": thread_id, "includeTurns": True})["thread"]
    if thread.get("historyMode") == "paginated":
        raise WakeError("This task uses paginated history, which Wake 0.1 does not support.")
    return thread


def wait_for_capacity(client, bucket, poll, max_wait, log=print, sleep=time.sleep):
    deadline = time.monotonic() + max_wait
    previous = None
    while time.monotonic() < deadline:
        state, reset = quota_state(client.call("account/rateLimits/read"), bucket)
        if state == "available":
            log("Usage is available. Checking the task before continuing.")
            return
        label = f"Usage {state}." + (f" Reported reset: {time.ctime(reset)}." if reset else "")
        if label != previous:
            log(label)
            previous = label
        # A timestamp is informational only. Never resume without a fresh capacity read.
        sleep(min(poll, max(0, deadline - time.monotonic())))
    raise WakeError("Maximum wait reached; task left stopped.")


def wait_for_turn(client, thread_id, turn_id, log=print):
    while True:
        if client.needs_attention:
            client.call("turn/interrupt", {"threadId": thread_id, "turnId": turn_id})
            raise WakeError("Task needs approval or input. Continue it in Codex.")
        try:
            event = client.events.get_nowait()
        except queue.Empty:
            client.receive(1)
            continue
        params = event.get("params", {})
        if params.get("threadId") != thread_id:
            continue
        if event.get("method") == "item/agentMessage/delta":
            print(params.get("delta", ""), end="", flush=True)
        if event.get("method") == "turn/completed" and params["turn"]["id"] == turn_id:
            return params["turn"]


def run(args, client, journal, log=print):
    active = None
    try:
        if args.command == "run":
            thread = client.call("thread/start", {"cwd": str(Path(args.project).resolve())})["thread"]
            thread_id = thread["id"]
            log(f"Task: {thread_id}")
            turn = client.call("turn/start", {"threadId": thread_id,
                "input": [{"type": "text", "text": args.prompt}]})["turn"]
            active = (thread_id, turn["id"])
            turn = wait_for_turn(client, *active, log)
            active = None
        else:
            thread_id = args.thread
            thread = read_task(client, thread_id)
            if thread.get("status", {}).get("type") == "active":
                raise WakeError("Task is active. Wake will not attach to running work.")
            turns = thread.get("turns", [])
            if not turns or not usage_failure(turns[-1]):
                raise WakeError("The latest turn did not fail with a Codex usage limit. Nothing to resume.")
            turn = turns[-1]
        retries = 0
        while usage_failure(turn):
            if retries >= args.max_resumes:
                raise WakeError("Automatic resume cap reached; task left stopped.")
            wait_for_capacity(client, args.bucket, args.poll, args.max_wait, log)
            latest = read_task(client, thread_id)
            latest_turns = latest.get("turns", [])
            if (latest.get("status", {}).get("type") == "active" or not latest_turns or
                    latest_turns[-1]["id"] != turn["id"] or not usage_failure(latest_turns[-1])):
                raise WakeError("Task changed while waiting. Wake will not continue it.")
            journal.claim(thread_id, turn["id"])
            resumed = client.call("thread/resume", {"threadId": thread_id})["thread"]
            if resumed.get("status", {}).get("type") == "active":
                raise WakeError("Task became active before dispatch. Resume cancelled.")
            new_turn = client.call("turn/start", {"threadId": thread_id,
                "input": [{"type": "text", "text": CONTINUE}]})["turn"]
            active = (thread_id, new_turn["id"])
            retries += 1
            log(f"Resumed task ({retries}/{args.max_resumes}).")
            turn = wait_for_turn(client, *active, log)
            active = None
        status = turn.get("status", "unknown")
        log(f"\nTask stopped: {status}.")
        if status != "completed":
            raise WakeError("This was not a usage-limit failure; open the task in Codex to continue.")
    finally:
        if active:
            try:
                client.call("turn/interrupt", {"threadId": active[0], "turnId": active[1]}, timeout=10)
            except Exception:
                log("Could not confirm interruption. Check the task in Codex before restarting Wake.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex", help="Codex executable name or path")
    parser.add_argument("--state-dir", default=str(Path.home() / ".wake-codex"))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Read-only check of connection and quota")
    sub.add_parser("list", help="List the 30 most recently updated local tasks")
    for command in ("run", "resume"):
        p = sub.add_parser(command)
        if command == "run":
            p.add_argument("prompt")
            p.add_argument("--project", default=".")
        else:
            p.add_argument("thread")
            p.add_argument("--exclusive", action="store_true", required=True,
                help="Confirm no other Codex client will run this task while Wake owns it")
        p.add_argument("--poll", type=int, default=60)
        p.add_argument("--max-resumes", type=int, default=3)
        p.add_argument("--max-wait", type=int, default=604800, help="Seconds to wait per interruption (default 7 days)")
        p.add_argument("--bucket", default="codex")
    args = parser.parse_args()
    if args.command in ("run", "resume") and (args.poll < 15 or args.max_resumes < 1 or args.max_wait < 1):
        parser.error("poll must be >=15 seconds; max-resumes and max-wait must be positive")
    client = journal = None
    try:
        if args.command in ("run", "resume"):
            journal = Journal(args.state_dir)
        client = Client(args.codex)
        if args.command == "doctor":
            state, reset = quota_state(client.call("account/rateLimits/read"))
            print(f"Codex connected. Usage: {state}. Next blocking reset: {reset or 'not reported'}")
        elif args.command == "list":
            for thread in client.call("thread/list", {"limit": 30, "sortKey": "updated_at"})["data"]:
                print(f"{thread['id']}  {thread.get('name') or thread.get('preview', '')[:70]}")
        else:
            run(args, client, journal)
    except KeyboardInterrupt:
        print("\nWake stopped.")
        return 130
    except (WakeError, OSError, ValueError, KeyError) as error:
        print(f"Wake: {error}", file=sys.stderr)
        return 1
    finally:
        if client:
            client.close()
        if journal:
            journal.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
