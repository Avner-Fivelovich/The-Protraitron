# Portraitron Multi-Agent Development Workflow

This document defines the optimized autonomous development loop for the Portraitron project. The parent orchestrator agent must strictly follow this loop for all tasks listed in [`TODO.md`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/TODO.md) on the `AI-agent` branch to maintain code quality while minimizing token consumption and quota usage.

---

## Core Rules & Safety Boundaries

> [!IMPORTANT]
> **Git Isolation**: All work must be conducted exclusively on the `AI-agent` branch. **Never** checkout/modify the `main` branch or execute `git push` to origin.

- **Auto-Approve & Sandbox Execution**: Ensure local environment configurations ([`.env`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/.env) and [`scripts/send_notification.py`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/scripts/send_notification.py)) are configured. In sandbox mode, email notifications are logged locally to prevent spam or authentication failures.
- **Alert on Blockers**: If a subagent encounters a blocker, requires physical/hardware intervention, or needs user confirmation, the parent orchestrator must trigger an email notification via [`scripts/send_notification.py`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/scripts/send_notification.py).
- **Session Warm Reuse**: Maintain active subagent conversation threads across iterations. Reuse existing agent conversations via `send_message` rather than spawning fresh subagents for every task to avoid repetitive context rehydration.

---

## Development Workflow Architecture

```mermaid
flowchart TD
    Start([Start Next Task in TODO.md]) --> Step1[Step 1: Develop\nDelegated to portraitron_developer]
    
    subgraph Step 1: Implementation
        Step1 --> Plan[1. Formulate Plan & Send Plain-English Email]
        Plan --> Execute[2. Code Implementation]
        Execute --> DevCommit[3. Commit to AI-agent branch]
    end

    DevCommit --> Step2[Step 2: Simplify & Refactor\nExecuted directly by Parent Agent]

    subgraph Step 2: Quality & Refinement
        Step2 --> Review[1. Review Code Changes]
        Review --> Refactor[2. Simplify Logic & Reduce Redundancy]
        Refactor --> RefactorCommit[3. Commit: Refactor and simplify]
    end

    RefactorCommit --> Step3[Step 3: Verify & Test\nExecuted directly by Parent Agent]

    subgraph Step 3: Verification & Status
        Step3 --> Test[Run Tests & Dry-Runs]
        Test --> Result{Outcome?}
        Result -->|Success| Success[Mark [x] in TODO.md & Commit]
        Result -->|Software Bug| Bug[Prepend Bug to Top of TODO.md & Commit]
        Result -->|Hardware / Manual Block| Block[Move to End with [BLOCKED/MANUAL], Send Email Alert & Commit]
    end

    Success --> NextTask{More Tasks?}
    Bug --> Step1
    Block --> NextTask
    NextTask -->|Yes| Start
    NextTask -->|No| Done([All Tasks Completed / Triaged])
```

---

## The Optimized Loop Sequence

For each task in [`TODO.md`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/TODO.md), the parent orchestrator executes the three sequential phases:

### Step 1: Develop (Delegated to `portraitron_developer`)
The parent orchestrator invokes the `portraitron_developer` subagent to write the core implementation:

1. **Plan & Notify**:
   - Read the next incomplete task from [`TODO.md`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/TODO.md).
   - Formulate an implementation strategy.
   - Translate the plan into a plain-English, jargon-free summary (avoid technical terms like APIs/libraries).
   - Send notification via parent-agent messaging / transcript logging:
     ```text
     [PLAN] <Task Name>: <Plain English Summary>
     ```
2. **Execute**: Write or update the necessary source files in the codebase (e.g., [`src/robot/controller.py`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/src/robot/controller.py)).
3. **Commit**: Commit completed work to the `AI-agent` branch:
   ```bash
   git commit -am "Implement: <Task Name>"
   ```
4. **Session Warm Reuse**: Keep the developer subagent conversation active and reuse it for subsequent implementation tasks via `send_message`.

---

### Step 2: Simplify & Refactor (Executed directly by Parent Agent)
To conserve token overhead and avoid unnecessary context passing, the parent orchestrator directly performs code review and refactoring:

1. **Review**: Examine the diff and changes introduced by the developer subagent.
2. **Refactor**:
   - Eliminate redundant logic and boilerplate.
   - Keep functions small, modular, and single-purpose (extract sub-tasks to helper functions).
   - Ensure proper error handling, type annotations, and docstrings.
3. **Commit**: Commit the refactored code:
   ```bash
   git commit -am "Refactor and simplify: <Task Name>"
   ```

---

### Step 3: Verify & Test (Executed directly by Parent Agent)
The parent orchestrator executes automated validation, updates the task tracking, and commits the state:

1. **Test Execution**: Run unit tests, integration tests, or dry-run scripts:
   ```bash
   ./venv/bin/python main.py --dryrun
   # or run specific test suites
   pytest tests/
   ```
2. **Task State Handling**:
   - **On Success**:
     - Mark task as completed `[x]` in [`TODO.md`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/TODO.md).
     - Commit changes:
       ```bash
       git commit -am "Verify and complete: <Task Name>"
       ```
   - **On Software Bug**:
     - Prepend the detailed bug description as a new incomplete task at the very top of [`TODO.md`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/TODO.md) so it will be prioritized on the next loop.
     - Commit changes:
       ```bash
       git commit -am "Report test failure on: <Task Name>"
       ```
   - **On Hardware or User Block**:
     - Move the task to the bottom of [`TODO.md`](file:///Users/avnerf/Documents/GitHub/The%20Protraitron/TODO.md) under the `## Physical & Hardware Tasks (Blocked / Manual)` section, prefixed with `[BLOCKED/MANUAL]`.
     - Flag blocker in agent logs:
       ```text
       [BLOCKER] <Task Name>: <Explanation of hardware dependency or required manual action>
       ```
     - Commit changes:
       ```bash
       git commit -am "Flag hardware/manual block on: <Task Name>"
       ```

---

## Commit & Notification Standards Reference

| Phase | Action | Commit Message Format | Notification Trigger |
|---|---|---|---|
| **Step 1: Develop** | Feature implementation | `Implement: <Task Name>` | `[PLAN] <Task Name>: <Summary>` |
| **Step 2: Refactor** | Code simplification & cleanup | `Refactor and simplify: <Task Name>` | None |
| **Step 3: Verify (Success)** | Test pass & task completion | `Verify and complete: <Task Name>` | None |
| **Step 3: Verify (Bug)** | Test failure & issue logging | `Report test failure on: <Task Name>` | None (queued in `TODO.md`) |
| **Step 3: Verify (Blocked)** | Hardware / physical dependency | `Flag hardware/manual block on: <Task Name>` | `[BLOCKER] <Task Name>: <Reason>` |
