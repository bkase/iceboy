# AGENTS.md

If you are working on a bead, commit after each bead is complete, and do NOT skip hooks
Do not run `tools/run_precommit_checks.sh` manually before `git commit`; rely on the commit hook to run it once unless a user explicitly asks for a standalone precommit run.

<!-- br-agent-instructions-v1 -->

---

## Beads Workflow Integration

This project uses [beads_rust](https://github.com/Dicklesworthstone/beads_rust) (`br`/`bd`) for issue tracking. Issues are stored in `.beads/` and tracked in git.

### Essential Commands

```bash
# View ready issues (unblocked, not deferred)
br ready              # or: bd ready

# List and search
br list --status=open # All open issues
br show <id>          # Full issue details with dependencies
br search "keyword"   # Full-text search

# Create and update
br create --title="..." --type=task --priority=2
br update <id> --status=in_progress
br close <id> --reason="Completed"
br close <id1> <id2>  # Close multiple issues at once

# Sync with git
br sync --flush-only  # Export DB to JSONL
br sync --status      # Check sync status
```

### Workflow Pattern

1. **Start**: Run `br ready` to find actionable work
2. **Claim**: Use `br update <id> --status=in_progress`
3. **Work**: Implement the task
4. **Complete**: Use `br close <id>`
5. **Sync**: Always run `br sync --flush-only` at session end

### Key Concepts

- **Dependencies**: Issues can block other issues. `br ready` shows only unblocked work.
- **Priority**: P0=critical, P1=high, P2=medium, P3=low, P4=backlog (use numbers 0-4, not words)
- **Types**: task, bug, feature, epic, question, docs
- **Blocking**: `br dep add <issue> <depends-on>` to add dependencies

### Session Protocol

**Before ending any session, run this checklist:**

```bash
git status              # Check what changed
git add <files>         # Stage code changes
br sync --flush-only    # Export beads changes to JSONL
git commit -m "..."     # Commit everything; let the commit hook run precommit checks
git push                # Push to remote
```

### Best Practices

- Check `br ready` at session start to find available work
- Update status as you work (in_progress → closed)
- Create new issues with `br create` when you discover tasks
- Use descriptive titles and set appropriate priority/type
- Always sync before ending session
- Do not run the full precommit script manually right before commit unless explicitly requested; the commit hook already runs it
- Prefer the native C++/Verilator harness over cocotb for longer-running ROM or raster tests. As a default rule, if a test is expected to run for more than `50_000` M-cycles, use the C++ harness unless there is a concrete reason not to.
- Use `Scripts/swiftpm-cache.sh` wrappers instead of raw `swift build`, `swift test`, or `swift run` in repo scripts and repeated local workflows
- Debug/test/run cache: `.build/apus-debug`
- Release/benchmark cache: `.build/apus-release`
- Benchmark commands must not reuse the debug scratch path or they will recompile `SwiftSyntax` release artifacts unnecessarily

### Fast Path Learnings

- For the Layer 2 unboxed frontend, prefer `RawSyntax` / `RawTokenSyntax` traversal over `Syntax` / `TokenSyntax` wrappers in hot loops.
- In the unboxed path, carry byte offsets manually and derive token spans from raw byte lengths instead of repeatedly querying `position`, `endPosition`, `leadingTrivia`, or `trailingTrivia` through SwiftSyntax wrappers.
- For trivia in the unboxed path, prefer scanning `sourceBytes` directly over materializing SwiftSyntax trivia collections when the tape contract only needs kind plus byte spans.
- Treat spelling interning as a hot path: reserve up front, avoid generic equality helpers in tight loops, and compare directly against source bytes when possible.
- When optimizing hot code, verify the release binary with assembly inspection, not just source review. Check for wrapper calls, retain/release traffic, append growth paths, and avoidable branches.
- Keep the baseline frontend available as a differential oracle. Any fast-path rewrite must preserve exact output parity against the baseline across the repository corpus.
- Benchmark changes with `Scripts/benchmark_frontend_differential.sh` and prefer median `unbox_us` on the real repo corpus over microbench assumptions.

<!-- end-br-agent-instructions -->
