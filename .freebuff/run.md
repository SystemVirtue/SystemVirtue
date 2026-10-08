# Running SystemVirtue MVP (this worktree)

## 1. Reproducing the artifacts a fresh checkout needs

This project is **Python 3.9 standard library only**. There is nothing to
install and nothing to copy:

- No package.json, lockfile, or virtualenv — no dependency install step.
- No env files (`.env.local` etc.) exist in the main checkout; all settings are
  environment variables with defaults (see section 2).
- `22_MVP/var/systemvirtue.db` is **generated runtime state**: on first run the
  server ingests `22_MVP/corpus/seed.json` automatically and creates the store.
- `22_MVP/corpus/seed.json` is committed and deterministic
  (`python3 22_MVP/corpus/build_seed.py` rebuilds it; not required).

Verify the checkout before serving (optional but recommended):

    cd 22_MVP && python3 -m unittest discover -s tests -t .

## 2. Running the server

    cd 22_MVP && SV_PORT=8791 python3 -u app/server.py

- `SV_PORT` selects the port (the app default is 8765; 8791 is this thread's
  preview port). `SV_DB` and `SV_EVENT_LOG` optionally override the store path
  and instrumentation log.
- Health check: `curl http://127.0.0.1:8791/api/health`

Detach so the server outlives the conversation (macOS, no `setsid`):

    { nohup python3 -u app/server.py > "<log>" 2>&1 < /dev/null & echo "pid=$!"; disown; }

Then confirm survival after ~5s with `kill -0 <pid>` (a vanished pid means the
runner reaped the process group — check the log before assuming a crash). If
reaped, relaunch under `launchctl submit -l <label> -- /bin/sh -c "exec
python3 -u app/server.py > <log> 2>&1"` and remove the job with
`launchctl remove <label>` when done.

This thread's preview: http://127.0.0.1:8791/ (log:
.freebuff/preview-96c0b601-e763-45be-b945-91c4c2311e11.log).
