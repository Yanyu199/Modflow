"""Runtime resource monitoring for worker/MF6 process trees."""

from __future__ import annotations

from typing import Any, Dict, Optional

from process_control import sample_process_tree, terminate_process_tree
from runtime_config import DEFAULT_RUNTIME_CONFIG, RuntimeConfig


class ResourceLimitExceeded(RuntimeError):
    def __init__(self, code: str, message: str, usage: Dict[str, Any], termination: Dict[str, Any]):
        super().__init__(message)
        self.code = code
        self.message = message
        self.usage = usage
        self.termination = termination


class ResourceController:
    """Best-effort OS resource guard based on process-tree sampling.

    This controller deliberately does not kill the Flask API process. It only
    receives worker/MF6 PIDs and enforces limits against those process trees.
    """

    def __init__(self, config: RuntimeConfig = DEFAULT_RUNTIME_CONFIG):
        self.config = config
        self.peak_rss_bytes = 0
        self.peak_cpu_seconds = 0.0
        self.samples = 0
        self.last_sample = None

    def sample(
        self,
        pid: int,
        *,
        process_group_id: Optional[int] = None,
        reason_prefix: str = "process",
    ) -> Dict[str, Any]:
        sample = sample_process_tree(pid)
        self.samples += 1
        self.last_sample = sample
        self.peak_rss_bytes = max(self.peak_rss_bytes, int(sample.get("rss_bytes") or 0))
        self.peak_cpu_seconds = max(self.peak_cpu_seconds, float(sample.get("cpu_seconds") or 0.0))

        memory_limit = int(self.config.max_process_memory_bytes or 0)
        if memory_limit > 0 and self.peak_rss_bytes > memory_limit:
            usage = self.usage(limit_exceeded="memory", limit_bytes=memory_limit)
            termination = terminate_process_tree(
                pid,
                process_group=process_group_id,
                grace_seconds=self.config.process_termination_grace_seconds,
                reason=f"{reason_prefix}_memory_limit",
            )
            raise ResourceLimitExceeded(
                "RUN_MEMORY_LIMIT_EXCEEDED",
                "Run process tree exceeded configured memory limit.",
                usage,
                termination,
            )

        cpu_limit = int(self.config.max_process_cpu_seconds or 0)
        if cpu_limit > 0 and self.peak_cpu_seconds > cpu_limit:
            usage = self.usage(limit_exceeded="cpu", limit_cpu_seconds=cpu_limit)
            termination = terminate_process_tree(
                pid,
                process_group=process_group_id,
                grace_seconds=self.config.process_termination_grace_seconds,
                reason=f"{reason_prefix}_cpu_limit",
            )
            raise ResourceLimitExceeded(
                "RUN_CPU_LIMIT_EXCEEDED",
                "Run process tree exceeded configured CPU time limit.",
                usage,
                termination,
            )

        return sample

    def usage(self, **extra) -> Dict[str, Any]:
        payload = {
            "monitor": "psutil_process_tree",
            "samples": int(self.samples),
            "peak_rss_bytes": int(self.peak_rss_bytes),
            "peak_cpu_seconds": float(self.peak_cpu_seconds),
            "last_sample": self.last_sample,
            "limits": {
                "max_process_memory_bytes": int(self.config.max_process_memory_bytes or 0),
                "max_process_cpu_seconds": int(self.config.max_process_cpu_seconds or 0),
            },
        }
        payload.update(extra)
        return payload
