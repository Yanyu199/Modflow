"""SQLite-backed single-machine scheduler claim store."""

from __future__ import annotations

import os
import socket
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from project_store import ProjectStore
from runtime_config import DEFAULT_RUNTIME_CONFIG, RuntimeConfig


CLAIM_ACTIVE_STATES = {"starting", "running"}


def new_owner_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:12]}"


class RunSchedulerStore:
    def __init__(self, project_store=None, config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG):
        self.project_store = project_store or ProjectStore()
        self.config = config
        self.path = Path(self.project_store.root) / ".run_scheduler.sqlite"
        self._init_db()

    def _connect(self):
        self.project_store.ensure_root()
        conn = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_claims (
                    run_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    flow_model_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    lease_owner TEXT,
                    lease_token TEXT,
                    lease_expires_at REAL,
                    heartbeat_at REAL,
                    worker_pid INTEGER,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_claims_state ON run_claims(state)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_run_claims_project_state ON run_claims(project_id, state)")

    def enqueue(self, manifest: Dict[str, Any]) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO run_claims
                (run_id, project_id, flow_model_id, state, created_at, updated_at)
                VALUES (?, ?, ?, 'queued', ?, ?)
                """,
                (manifest["run_id"], manifest["project_id"], manifest["flow_model_id"], now, now),
            )

    def try_claim(
        self,
        manifest: Dict[str, Any],
        *,
        owner_id: str,
        max_concurrent: int,
        max_per_project: int,
        lease_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        self.enqueue(manifest)
        now = time.time()
        expires = now + int(lease_seconds)
        token = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                self._expire_stale_locked(conn, now)
                active = conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM run_claims
                    WHERE state IN ('starting', 'running') AND lease_expires_at > ?
                    """,
                    (now,),
                ).fetchone()["count"]
                if int(active) >= int(max_concurrent):
                    conn.execute("ROLLBACK")
                    return None
                project_active = conn.execute(
                    """
                    SELECT COUNT(*) AS count FROM run_claims
                    WHERE project_id = ? AND state IN ('starting', 'running') AND lease_expires_at > ?
                    """,
                    (manifest["project_id"], now),
                ).fetchone()["count"]
                if int(project_active) >= int(max_per_project):
                    conn.execute("ROLLBACK")
                    return None
                cur = conn.execute(
                    """
                    UPDATE run_claims
                    SET state = 'starting',
                        lease_owner = ?,
                        lease_token = ?,
                        lease_expires_at = ?,
                        heartbeat_at = ?,
                        updated_at = ?
                    WHERE run_id = ? AND state = 'queued'
                    """,
                    (owner_id, token, expires, now, now, manifest["run_id"]),
                )
                if cur.rowcount != 1:
                    conn.execute("ROLLBACK")
                    return None
                conn.execute("COMMIT")
                return {"owner_id": owner_id, "lease_token": token, "lease_expires_at": expires}
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def mark_running(self, run_id: str, *, owner_id: str, lease_token: str, worker_pid: int) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE run_claims
                SET state = 'running', worker_pid = ?, heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
                WHERE run_id = ? AND lease_owner = ? AND lease_token = ?
                """,
                (
                    int(worker_pid or 0),
                    now,
                    now + int(self.config.scheduler_lease_seconds),
                    now,
                    run_id,
                    owner_id,
                    lease_token,
                ),
            )

    def heartbeat(self, run_id: str, *, owner_id: str, lease_token: str) -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE run_claims
                SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
                WHERE run_id = ? AND lease_owner = ? AND lease_token = ? AND state IN ('starting', 'running')
                """,
                (now, now + int(self.config.scheduler_lease_seconds), now, run_id, owner_id, lease_token),
            )

    def finish(self, run_id: str, state: str = "terminal") -> None:
        now = time.time()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE run_claims
                SET state = ?, lease_expires_at = NULL, heartbeat_at = ?, updated_at = ?
                WHERE run_id = ?
                """,
                (state, now, now, run_id),
            )

    def cancel(self, run_id: str) -> None:
        self.finish(run_id, "cancelled")

    def _expire_stale_locked(self, conn, now: float) -> None:
        conn.execute(
            """
            UPDATE run_claims
            SET state = 'queued',
                lease_owner = NULL,
                lease_token = NULL,
                lease_expires_at = NULL,
                worker_pid = NULL,
                updated_at = ?
            WHERE state IN ('starting', 'running') AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
            """,
            (now, now),
        )

    def stats(self) -> Dict[str, Any]:
        now = time.time()
        with self._connect() as conn:
            self._expire_stale_locked(conn, now)
            rows = conn.execute("SELECT state, COUNT(*) AS count FROM run_claims GROUP BY state").fetchall()
            return {
                "backend": "sqlite",
                "supports_single_machine_multi_process": True,
                "supports_multi_node": False,
                "states": {row["state"]: int(row["count"]) for row in rows},
                "lease_seconds": int(self.config.scheduler_lease_seconds),
            }
