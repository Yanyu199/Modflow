# Process Lifecycle

This project now treats a model run as three related identities:

- The API or run-worker executor, identified by an owner id.
- The Python worker process, recorded as `executor.worker_pid` plus `worker_identity`.
- The MF6 child process, recorded as `executor.mf6_pid`, `mf6_identity`, and `process_group_id` where available.

## Cancellation

Cancellation first moves a non-terminal run to `cancel_requested`. The executor then terminates the worker process tree and the MF6 process tree using `process_control.terminate_process_tree()`. The helper uses psutil for recursive process-tree termination on Windows and Linux/macOS, and also attempts process-group termination on POSIX when a process group id is known.

The final state is:

- `cancelled` when all known process ids are gone.
- `failed_cancel` when cancellation was requested but known pids remain alive.

Completed runs are terminal and cannot be cancelled.

## Timeout

MF6 timeout is enforced inside `RunService._execute_mf6()`. When `FLOPY_RUN_TIMEOUT_SECONDS` is exceeded, the same process-tree termination helper is used. The run is marked `timed_out`; stdout/stderr and input/output files remain in the run directory.

## Recovery

On embedded executor startup, non-terminal worker states are recovered by reading persisted process identities. If a recorded worker or MF6 process still matches the saved PID identity, the executor terminates it before marking the run terminal. Running runs are not blindly restarted.

Dedicated worker mode uses the same recovery logic when `python -m run_worker` starts.

## Manifest Fields

Run manifest schema `1.2` adds:

- `executor.owner_id`
- `executor.lease_token`
- `executor.worker_identity`
- `executor.mf6_identity`
- `executor.process_group_id`
- `executor.termination`
- `executor.run_duration_seconds`
- `resource_usage`

These fields are diagnostic and must not contain server absolute paths.
