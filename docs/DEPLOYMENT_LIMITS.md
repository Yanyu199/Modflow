# Deployment Limits

## Executor Modes

Development can use embedded execution:

```bash
set FLOPY_EXECUTOR_MODE=embedded
python app.py
```

Dedicated worker mode keeps API processes from scheduling runs directly:

```bash
set FLOPY_EXECUTOR_MODE=dedicated
python app.py
python -m run_worker
```

The current scheduler is SQLite-backed and supports single-machine, multi-API-worker deployments. It is not a distributed multi-node queue.

## Scheduling Guarantees

The SQLite scheduler stores only run claim state. Project data remains in the existing project store. Claiming is transactional:

```text
queued -> starting
```

Global limits are enforced in the scheduler transaction:

- `FLOPY_MAX_CONCURRENT_RUNS`
- `FLOPY_MAX_RUNS_PER_PROJECT`
- `FLOPY_SCHEDULER_LEASE_SECONDS`

Lease expiry allows stale claims to return to `queued`.

## OS Resource Protection

The current implementation uses psutil process-tree monitoring. It records peak RSS and CPU seconds and terminates the run process tree if:

- `FLOPY_MAX_PROCESS_MEMORY_BYTES` is exceeded.
- `FLOPY_MAX_PROCESS_CPU_SECONDS` is set and exceeded.

This is a practical monitor-based guard, not a kernel hard limit. Future Linux deployments should consider cgroups/systemd scopes or container limits; future Windows deployments may add Job Object limits.

## Result Cache Memory

Result cache is per API process. Total deployment cache budget is:

```text
api_worker_count * FLOPY_MAX_RESULT_CACHE_BYTES
```

Set `FLOPY_RESULT_CACHE_ENABLED=false` or lower `FLOPY_MAX_RESULT_CACHE_BYTES` for memory-constrained deployments.
