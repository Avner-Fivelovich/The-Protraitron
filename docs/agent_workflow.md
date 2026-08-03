# Portraitron Multi-Agent Development Workflow

This document defines the optimized autonomous development loop. The parent orchestrator agent must strictly follow this loop for all tasks listed in `TODO.md` on the `AI-agent` branch to minimize token consumption and quota usage.

## Core Rules & Boundaries
- **Git Isolation**: All work must be done on the `AI-agent` branch. **Never** interact with the `main` branch or run `git push` to origin.
- **Auto-Approve / Sandbox**: Make sure to check that the local `.env` and `scripts/send_notification.py` are used for alerts.
- **Alert on Blockers**: If a subagent gets stuck, requires manual intervention, or needs confirmation, the parent orchestrator must use `scripts/send_notification.py` to send an email alert to the user.

---

## The Optimized Loop Sequence

For each task in `TODO.md`, the parent orchestrator executes the following phases:

### Step 1: Develop (Delegated to `portraitron_developer`)
The parent orchestrator invokes the `portraitron_developer` subagent to write the core implementation:
1. **Plan & Notify**: Read the next incomplete task from `TODO.md`. Formulate a plan, translate it to a plain-English, jargon-free summary (no technical terms like APIs/libraries), and email it using:
   ```bash
   ./scripts/send_notification.py "[PLAN] <Task Name>" "<Plain English Summary>"
   ```
2. **Execute**: Write the implementation in the codebase (e.g. modifying `src/robot/controller.py`).
3. **Commit**: Commit completed work to the `AI-agent` branch.
4. **Session Warm Reuse**: The parent orchestrator should keep this subagent conversation active and reuse it for subsequent development tasks via `send_message` rather than spawning a fresh subagent each time.

### Step 2: Simplify & Refactor (Executed directly by Parent Agent)
To save token overhead, the parent agent (Antigravity) directly performs the refactoring step:
1. **Review**: Examine the changes made by the developer.
2. **Refactor**: Apply edits directly to simplify the logic, remove redundant code, improve readability, and keep functions small and focused (delegating sub-tasks to helper functions).
3. **Commit**: Commit the refactored code with: `Refactor and simplify: <Task Name>`.

### Step 3: Verify & Test (Executed directly by Parent Agent)
The parent agent directly executes testing and updates the status:
1. **Test**: Run verification and dry-run scripts (e.g., `./venv/bin/python main.py --dryrun` or scripts inside `./tests`).
2. **Update TODO.md & Commit**:
   - **On Success**: Mark the task completed `[x]` in `TODO.md`. Commit changes: `git commit -am "Verify and complete: <Task Name>"`.
   - **On Software Bug**: Prepend the bug details as a new incomplete task at the very top of `TODO.md` so the developer will pick it up on the next loop. Commit changes: `git commit -am "Report test failure on: <Task Name>"`.
   - **On Hardware or User Block**: Move the task to the very end of `TODO.md` prefixed with `[BLOCKED/MANUAL]`. Commit changes: `git commit -am "Flag hardware/manual block on: <Task Name>"`.
