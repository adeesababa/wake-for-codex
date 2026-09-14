# Wake

A small local tool that continues a Codex task after a usage-limit interruption.

**Prototype · Python 3.10+ · Codex CLI with ChatGPT sign-in required.** Independent project; not affiliated with OpenAI. Wake does not reset limits, buy credits, or switch accounts.

## Start

Download this repository and open a terminal in its folder. Install the [Codex CLI](https://learn.chatgpt.com/docs/cli) and sign in with `codex login` first.

```sh
python wake.py doctor
python wake.py run "Finish the task and run the relevant checks" --project "/path/to/project"
```

On Windows use the real project path, for example `--project "C:\Projects\my-app"`. If `python` is unavailable, try `py`. The computer must remain awake, online, and running Wake. It does not wake the computer or install a startup service.

Already interrupted in the middle of a task?

```sh
python wake.py list
python wake.py resume TASK_ID --exclusive
```

Replace `TASK_ID` with the ID printed by `list`. `--exclusive` means you will leave this task stopped in other clients while Wake runs it. **Only the latest turn failing with the structured `usageLimitExceeded` error qualifies.** A successful, cancelled, active, or unrelated failed task will not restart.

The safest workflow is to start the task through Wake. Resuming a desktop-created task is experimental: it runs through a separate local app-server, and desktop-only tools or paginated histories may be unavailable. This is not a desktop-wide background watcher. Never run the same task in another client concurrently; checks across independent app-server processes cannot provide atomic exclusion. Paginated task histories are explicitly rejected in version 0.1.

## What happens

1. Wake runs the selected task with Codex's configured model, sandbox, and permissions.
2. A structured usage-limit failure pauses execution.
3. Wake checks account capacity every 60 seconds. Both reported windows must have room. Missing data leaves it waiting. A reset timestamp alone never triggers a continuation.
4. Wake checks that the interrupted turn is still the latest turn, records a dispatch claim, and sends a continuation in the same task.
5. Completion, cancellation, other errors, required input, or an approval request stops automatic work. A successful turn is not repeatedly prodded to do more work.

By default there are at most three automatic continuations per invocation and seven days of waiting per interruption. Change these explicitly:

```sh
python wake.py resume TASK_ID --exclusive --max-resumes 2 --max-wait 86400 --poll 60
```

For a different metered model bucket, pass `--bucket BUCKET_ID`. Wake defaults to `codex`; it never guesses an unavailable bucket. Non-ChatGPT providers and missing quota information may be unsupported. `--codex PATH` before the subcommand selects an executable outside PATH.

## Stop and recovery

Press Ctrl+C. Wake requests interruption of a turn it started, then exits. If the connection is lost, check the task before restarting.

State lives in `~/.wake-codex` (under your Windows user folder on Windows). A single watcher lock prevents two Wake processes using that state directory. A claim is saved **before** dispatch, so a crash or timeout will not blindly duplicate the continuation. This deliberately favors manual recovery over repeating uncertain work.

After a forced shutdown, first verify that no Wake process or Codex task is running. Then remove `watch.lock` from that directory if it is stale. If `state.json` contains a dispatch claim but no continuation was ever started, inspect the task in Codex and continue manually. Do not clear claims just to force a retry. Use the same state directory across launches; separate copies or state directories defeat the lock. State contains task/turn IDs and timestamps, not credentials or conversations.

## Verification

```sh
python -m unittest -v
```

All 11 tests passed on Windows. Tests cover quota windows, missing data, reset verification, task eligibility, changed tasks, duplicate dispatch prevention, and cancellation. Protocol fields were checked against Codex CLI 0.153.4 generated schemas. A live account connection and a real task returning a fixed text reply both passed, including completion detection. Mocked reset tests do not establish real-account reset behavior; complete an actual overnight reset test before selling or relying on unattended production work.

## Project page

`docs/index.html` is the GitHub Pages documentation site. Open it locally or publish using `PUBLISH.md`. The website cannot run local Codex by itself. `BUSINESS.md` assesses a $0.99 price. No checkout or payment account is configured.

## Privacy and permissions

Wake starts the installed Codex executable and communicates locally over stdin/stdout. Codex handles authentication and its usual communication with OpenAI. Wake has no analytics, separate backend, credential scraping, or automatic approval bypass. Normal Codex execution may edit files and run commands according to the user's existing permissions. Requests requiring interactive approval or answers are returned as unsupported and the turn is interrupted for manual attention.

## Technical basis

Uses the [official app-server protocol](https://learn.chatgpt.com/docs/app-server): initialize, start/read/resume threads, start/interrupt turns, and read account rate limits. App-server and desktop compatibility can change; this prototype is not a guaranteed extension API for every Codex build.
