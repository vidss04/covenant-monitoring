"""Append-only JSON Lines audit log with a SHA-256 hash chain (tamper-evident)."""
import hashlib
import json
import subprocess
import time
import uuid
from pathlib import Path

from cov.common import ROOT, to_jsonable


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "uncommitted"


class AuditLog:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _last_hash(self):
        if not self.path.exists():
            return "GENESIS"
        last = None
        with self.path.open() as f:
            for ln in f:
                if ln.strip():
                    last = ln
        return json.loads(last)["entry_hash"] if last else "GENESIS"

    def append(self, kind, payload):
        rec = {"entry_id": str(uuid.uuid4()), "kind": kind, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "prev_hash": self._last_hash(), "payload": to_jsonable(payload)}
        body = json.dumps(rec, sort_keys=True, default=str)
        rec["entry_hash"] = hashlib.sha256(body.encode()).hexdigest()
        with self.path.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        return rec

    def entries(self):
        if not self.path.exists():
            return []
        return [json.loads(l) for l in self.path.read_text().splitlines() if l.strip()]

    def verify_chain(self):
        prev = "GENESIS"
        for i, rec in enumerate(self.entries()):
            h = rec.pop("entry_hash")
            if rec["prev_hash"] != prev:
                return False, i
            if hashlib.sha256(json.dumps(rec, sort_keys=True, default=str).encode()).hexdigest() != h:
                return False, i
            prev = h
        return True, None
