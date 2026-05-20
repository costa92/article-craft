# Verify-Claims Flag Validation (B8)

**Status**: design (not implemented — scoped for future multi-phase execution)
**Date**: 2026-05-20
**Target version**: TBD — multi-phase (estimated 3 release cycles)
**Author**: costa
**Backlog ref**: B8 in `docs/research/2026-05-20-feature-candidates.md`
**Predecessor**: v1.4.x `verify_claims.py` (the MVP `command -v TOOL` checker)

---

## 0. Problem statement

`scripts/verify_claims.py` ships as the MVP that catches a real
class of bug: an article tells the reader to run a command using a
tool that isn't actually installed on PATH. Today it answers exactly
one question: *does `command -v TOOL` succeed?*

It does **not** catch the next class of bug right above that one:
the tool exists, but the article calls it with a **flag that doesn't
exist** (or was renamed across a version bump). Examples we've
shipped in practice:

| Mistake | What happens |
|---------|--------------|
| `kubectl describe pod foo --output yaml` | `--output` isn't valid on `describe` — `-o` is. Article doesn't run. |
| `docker run -i --tty --rm ubuntu` | OK, this one's fine. But `docker run -t --interactive` (long+short mix) is fine too. The detector needs to handle equivalences. |
| `uv pip install requests --frozen-lockfile` | `--frozen` exists; `--frozen-lockfile` is npm's, not uv's. |
| `gh pr create --reviewer @me` | `--reviewer` takes a user, not `@me`. Different problem class but related. |
| `git checkout -b feature --base main` | `--base` doesn't exist on `git checkout`; it's a `gh pr create` flag. |

The MVP scope deliberately deferred this ("Intentionally out of scope
for now: flag-level validation" — `verify_claims.py:17-19`). v1.6.x
backlog item B8 promotes it from deferred to spec'd.

---

## 1. Design goals

1. **Catch the most common mistakes.** A small set of high-frequency
   tools (`kubectl`, `docker`, `git`, `uv`, `gh`, `pip`, `npm`,
   `curl`) cover ~80% of shell-block content in tech articles.
2. **No live execution.** Flag validation must work without running
   `tool --help` or `tool subcommand --help` at validation time
   (slow, breaks offline use, version-sensitive). Schemas are static.
3. **Severity-aware.** Unknown flags are WARN (might be a typo, but
   could be a new flag the schema hasn't been updated for); only
   flag-prefix collisions (like `--output` where the tool only has `-o`)
   that look more like typos are surfaced more aggressively.
4. **Versioned schemas.** Tool flags change. Schemas declare what
   version they target; verify reports schema age alongside findings
   so users know whether to update the schema before fixing the article.
5. **Composable with the existing MVP.** Today verify_claims emits
   `command_not_found` findings. Flag validation adds
   `unknown_flag` / `deprecated_flag` finding kinds. Same JSON shape,
   same exit-code semantics.
6. **Zero false-positive crashes.** A tool not in the schema set is
   silently skipped — never blocks a release just because we haven't
   curated its flags yet.

---

## 2. Non-goals (explicitly)

- ❌ **Auto-generating schemas from `tool --help`.** Tempting but
  brittle: every tool has a different help format, GNU vs BSD
  conventions, `--help -a` vs `--help-all`, etc. Hand-curated
  schemas with explicit version targets ship faster and break less.
- ❌ **Validating flag *arguments*.** `kubectl get pods -n NS` —
  validating that `NS` is a real namespace is out of scope. Only the
  flag *name* is checked.
- ❌ **Subcommand validation.** `git foo` (no such git subcommand) is
  caught by the existing `command -v` (sort of — `git` is on PATH;
  the subcommand fails at runtime). Subcommand validation is a
  separate concern (likely v2 of this spec).
- ❌ **Schema for every tool a user might mention.** Top 8 tools
  ship; rest are silently skipped (no warnings, no errors).
- ❌ **Per-OS schema variants.** macOS `sed` vs GNU `sed` differ in
  flag syntax. Cross-platform articles are rare in our corpus; if
  they appear, the right answer is the article should call out the
  platform, not have the validator branch.
- ❌ **Auto-fixing unknown flags.** Like spell-check suggesting
  similar words, this is tempting but rarely correct (`--output`
  could be the user wanting JSON output AND wanting to use
  `--object` from a different version). Suggest-only, no auto-fix.

---

## 3. Architecture

### 3.1 Schema format

New module `scripts/tool_schemas/` (a directory — each tool gets its
own file for readability and per-tool version tracking).

```python
# scripts/tool_schemas/kubectl.py
SCHEMA = {
    "tool": "kubectl",
    "version_target": "1.30",     # The kubectl version this schema reflects
    "last_audited": "2026-05-20",  # Manual audit date
    "global_flags": {
        # Flags accepted by `kubectl` itself, before any subcommand
        "-n", "--namespace",
        "-A", "--all-namespaces",
        "--context",
        "--kubeconfig",
        "-v", "--v",
        "-o", "--output",
        "--server",
        "--token",
    },
    "subcommand_flags": {
        # Per-subcommand flag sets. The detector matches `kubectl <subcmd>`
        # and applies the matching set.
        "get":      {"-w", "--watch", "-l", "--selector", "--field-selector", ...},
        "describe": {"-f", "--filename", "--show-events", ...},
        "apply":    {"-f", "--filename", "-R", "--recursive", "--prune", ...},
        "delete":   {"-f", "--filename", "--grace-period", "--force", ...},
        # ... ~10 most-used subcommands ...
    },
    "deprecated_flags": {
        # Flag → "use X instead" — surfaces as a separate finding kind
        "--export": "Removed in 1.18; copy the resource manually.",
    },
}
```

### 3.2 Schema registry

```python
# scripts/tool_schemas/__init__.py

_SCHEMAS: dict[str, dict] = {}

def register(schema: dict) -> None:
    _SCHEMAS[schema["tool"]] = schema

def get(tool: str) -> dict | None:
    return _SCHEMAS.get(tool)

# At import:
from . import kubectl, docker, git, uv, gh, pip, npm, curl
register(kubectl.SCHEMA)
register(docker.SCHEMA)
# ...
```

### 3.3 Detection

Extend `verify_claims.py` parser to also extract **flags** per
command, not just the tool token. For each shell command:

```
$ kubectl get pods --watch -n default --field-selector status.phase=Running
   ^tool  ^sub   ^pos1  ^flag1   ^flag2     ^flag3-with-value
```

Walk tokens left-to-right; classify by leading char:

- Starts with `-` → flag
- Otherwise → positional (treat first positional after tool as subcommand
  candidate)

For each flag found, consult `tool_schemas.get(tool)`:

- `get(tool) is None` → skip (no schema, no opinion)
- Flag in `global_flags` OR in `subcommand_flags[subcmd]` → OK
- Flag in `deprecated_flags` → WARN with the migration hint
- Otherwise → WARN "unknown flag for kubectl 1.30; check schema or run
  kubectl get --help"

### 3.4 Output format

Existing `verify_claims.py` emits findings of the form:

```json
{
  "kind": "command_not_found",
  "tool": "yt-dlp",
  "line": 42,
  "context": "yt-dlp 'https://...'",
  "fix": "pip3 install yt-dlp"
}
```

Add two new kinds:

```json
{
  "kind": "unknown_flag",
  "tool": "kubectl",
  "subcommand": "describe",
  "flag": "--output",
  "line": 42,
  "context": "kubectl describe pod foo --output yaml",
  "schema_version": "1.30",
  "schema_audited": "2026-05-20",
  "hint": "kubectl describe doesn't have --output (use `-o` on `get`)."
}

{
  "kind": "deprecated_flag",
  "tool": "kubectl",
  "flag": "--export",
  "line": 88,
  "migration": "Removed in 1.18; copy the resource manually.",
  ...
}
```

Exit codes unchanged: 0 = clean, 1 = any finding, 2 = invalid usage.

### 3.5 CLI

`verify_claims.py scan` gets new flags:

- `--schema-only` — only emit findings that match a schema (skip
  command-not-found; useful for partial audits)
- `--no-flags` — disable flag validation entirely (regress to MVP
  behavior; for users with custom tooling whose schemas don't apply)

---

## 4. Implementation phases

### Phase 1 — Schema infrastructure + 2 tools (1 release)

**Scope**: Land the registry and the most-impactful schemas. Proves
the abstraction works.

**Deliverables**:

- `scripts/tool_schemas/__init__.py` registry
- `scripts/tool_schemas/kubectl.py` (target k8s 1.30)
- `scripts/tool_schemas/docker.py` (target Docker 26.x)
- `verify_claims.py` extended to extract flags per command, route
  through registry, emit new `unknown_flag` / `deprecated_flag` findings
- `tests/test_tool_schemas.py` — schema lookup, flag classification,
  positional vs flag distinguishing
- `tests/test_verify_claims_flags.py` — end-to-end via verify_claims
  on fixture article snippets

**Done when**: An article with `kubectl describe pod --output yaml`
or `docker run --interactive-tty` (typo) emits a structured
`unknown_flag` finding.

**Estimated effort**: 4–6 hours. Risk: low — additive, no behavior
change for articles without the targeted tools.

### Phase 2 — Tools 3–8 (1 release)

**Scope**: Add `git`, `uv`, `gh`, `pip`, `npm`, `curl`.

**Deliverables**:

- Six more schema files
- Per-tool audit notes (`last_audited` field)
- Tests stay in `tests/test_tool_schemas.py` but cover the new schemas

**Done when**: 8 tools have curated schemas. Articles mentioning any
of these get flag-level feedback.

**Estimated effort**: 1–2 hours per tool × 6 = 6–12 hours. Can be
split across releases.

### Phase 3 — Schema-staleness reporter (1 release)

**Scope**: Tiny tool that reports schema age. Reminds the
maintainer to re-audit.

**Deliverables**:

- `python3 scripts/verify_claims.py schemas` subcommand prints a
  table: tool → version_target → last_audited → days since audit
- Doctor.py optionally surfaces schemas older than 365 days as WARN
- CONTRIBUTING.md / scripts/README.md gets a "how to refresh a
  schema" section (manual procedure: run `tool --help`, diff against
  existing schema, update)

**Done when**: A user runs `doctor --schemas` and sees which schemas
need refresh.

**Estimated effort**: 2–3 hours.

---

## 5. Risks

### 5.1 Schema drift

**Risk**: Tools add/remove flags between releases. Schema reflects
2026 state; by 2027 some flags are wrong. False-positive
`unknown_flag` findings annoy users; false-negative misses real
typos.

**Mitigation**:

- Schemas declare `version_target` explicitly — users know what they're
  getting
- Phase 3's age reporter creates pressure to refresh
- Severity is WARN, not BLOCK — even false positives don't break
  publishing
- The "hint" field in `unknown_flag` findings explicitly says "check
  schema or run `tool --help`" so users can investigate quickly

### 5.2 False positives from common-but-rare flags

**Risk**: `kubectl` has many obscure global flags (`--profile`,
`--log-file`, etc.) that real-world articles rarely use. If the
schema doesn't list them, articles using them get false-positive
findings.

**Mitigation**:

- Phase 1's audit explicitly captures *all* documented global flags
  for the targeted version, not just the common subset
- Per-subcommand flag lists are more selective (only the documented
  ones for that subcommand) — there's no "global" leak
- Issue tracker can collect "this flag should be in the schema" reports

### 5.3 Schema maintenance cost

**Risk**: 8 tools × periodic audit = real time investment. If
nobody refreshes the schemas they decay and either WARN-spam or
silent-pass.

**Mitigation**:

- Phase 3's age reporter surfaces stale schemas
- Schema files live in one directory with a clear "how to audit"
  section in README — anyone can update one without touching the
  other 7
- Phase 4 (not in this spec) could explore semi-automated extraction
  from `--help` output for tools with well-structured help text

### 5.4 Subcommand parsing edge cases

**Risk**: `kubectl get --raw /api/v1/pods` — the `--raw` flag takes
a value that doesn't start with `-`, easy. But `git log --since='2
days ago'` — flag value has spaces and shell-quoting. Our token
walker might break.

**Mitigation**:

- Phase 1's parser explicitly tests these cases (test fixtures
  contain a stress suite of real-world commands from shipped
  articles)
- When ambiguous, treat as "can't parse → skip with INFO finding"
  rather than crash or false-positive

### 5.5 Tooling ecosystem churn (uv-style)

**Risk**: `uv` is a young tool. Its flag set evolves monthly. The
schema we ship today is wrong in three months.

**Mitigation**:

- Choose tools for Phase 1 / 2 with **stable** flag sets first
  (`kubectl`, `docker`, `git`, `gh` are mature). Add `uv` last with
  a 30-day refresh cadence explicitly documented.

---

## 6. Open questions (resolve before Phase 1)

1. **Subcommand vs global flag precedence**: if `kubectl --foo get
   pods`, is `--foo` a kubectl global flag or a `get` subcommand
   flag? Recommendation: **try global first**. Global flags appear
   before the subcommand canonically; subcommand-specific flags
   after. If not in either, WARN.
2. **Schema file location**: `scripts/tool_schemas/kubectl.py` (one
   per file) vs `scripts/tool_schemas.json` (one big JSON)?
   Recommendation: **one Python file per tool**. Python lets us
   include comments / migration hints / version-specific notes
   inline; JSON forces external docs.
3. **Severity for unknown flag**: WARN or ERROR? Recommendation:
   **WARN** in Phase 1. Promote to ERROR for specific tool-flag
   combinations only when we have evidence of real-world author
   confusion (Phase 2+).
4. **What about chained commands**: `kubectl get pods | grep Running |
   awk '{print $1}'`? Recommendation: **parse first command only**.
   `grep` and `awk` are POSIX-stable and rarely typo'd; their schemas
   aren't worth the audit cost.
5. **Should schemas ship in the plugin or be configurable?**
   Recommendation: **ship in plugin**. Per-user schema overrides
   (env.json `tool_schema_overrides`) is a v3 feature if anyone asks
   for it.

---

## 7. Concrete next step (when Phase 1 starts)

1. Create `scripts/tool_schemas/__init__.py` with the registry
   helpers (`register`, `get`).
2. Create `scripts/tool_schemas/kubectl.py` with a minimal schema:
   `global_flags`, `subcommand_flags` for ~5 most-used subcommands
   (`get`, `apply`, `delete`, `describe`, `logs`), `deprecated_flags`
   empty initially.
3. Extend `verify_claims.py`'s token walker to capture flags after
   the tool token. Add `unknown_flag` finding emission.
4. Write `tests/test_tool_schemas.py` covering: schema lookup,
   `kubectl get --watch` (known), `kubectl describe --output yaml`
   (unknown — `--output` is a `get` flag, not `describe`),
   `kubectl --foo bar` (global unknown).
5. Verify the existing `tests/test_verify_claims_flags.py` (or
   equivalent) tests still pass — Phase 1 must be **purely additive**
   to today's behavior.

This document is the contract — when someone picks up Phase 1 later,
they should be able to start coding from the architecture in §3 and
the deliverable list in §4 without re-deriving any design decision.
