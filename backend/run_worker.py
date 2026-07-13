"""Dedicated run worker entrypoint.

Usage:
    python -m run_worker
"""

from __future__ import annotations

from project_store import ProjectStore
from run_executor import LocalProcessRunExecutor
from runtime_config import DEFAULT_RUNTIME_CONFIG


def main():
    executor = LocalProcessRunExecutor(
        ProjectStore(),
        DEFAULT_RUNTIME_CONFIG,
        auto_start=True,
        recover_on_start=True,
    )
    print("run-worker started")
    print(f"executor owner: {executor.owner_id}")
    executor.serve_forever()


if __name__ == "__main__":
    main()
