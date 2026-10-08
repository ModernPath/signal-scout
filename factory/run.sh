#!/usr/bin/env bash
# Agent factory: one agent brief in, one reviewed draft change out.
#
#   bash factory/run.sh factory/briefs/001-<slug>.md
#
# The change is a new agents/<slug>/ copied from agents/example-agent/ and built
# following agents/AGENTS.md, plus specs/features/<slug>/. Headless agents do
# the thinking; this script runs the gates, which no model can talk its way past:
#
#   spec -> [spec gate] -> scaffold (script) -> test -> [test gate] -> [RED gate]
#        -> implement -> [scope gate] -> [GREEN gate] -> [hygiene gate]
#        -> register (script) -> review -> [verdict gate] -> PR text
#
# Settings (environment):
#   FACTORY_BACKEND        claude (default) | codex | opencode | fake (tests only)
#   FACTORY_MODEL          model for claude/opencode stages (opencode: provider/model)
#   FACTORY_RUN_ID         run id; default the brief id. A new id starts fresh.
#   FACTORY_MAX_TURNS      agent turns per stage (claude), default 60
#   FACTORY_STAGE_TIMEOUT  seconds per stage, default 1800
#   FACTORY_MAX_COST_USD   budget for the whole run (claude), default 15.00
#   FACTORY_RETRIES        retries of a stage the provider rate-limited, default 3
#   FACTORY_RETRY_WAIT     seconds to wait before each retry, default 65
#   FACTORY_IMPLEMENT_PASSES  implement passes before stopping, default 8 (each retries with the failing output)
#   FACTORY_REVIEW_ROUNDS  times review findings are fixed and re-reviewed, default 2
#   FACTORY_PR             file (default): write pr.md | gh: open a draft PR
#   FACTORY_PYTHON         interpreter with the agent's requirements, default python3
#   FACTORY_TEST_CMD       replaces the test command (see factory/check.sh)
#   FACTORY_BASE           branch to start from and diff against, default main
#
# Everything a run produces is in factory/runs/<run id>/: log, state file,
# each stage's agent output, spec.md, gate outputs, review.json, pr.md, and
# stop.md when the run stopped for a person.

set -uo pipefail
export PYTHONDONTWRITEBYTECODE=1

main() {
  ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || { echo "run.sh: not inside a git repository" >&2; exit 2; }
  cd "$ROOT" || exit 2

  BRIEF=${1:-}
  [ -n "$BRIEF" ] && [ -f "$BRIEF" ] || { echo "usage: bash factory/run.sh factory/briefs/<nnn>-<slug>.md" >&2; exit 2; }
  AGENT=$(sed -n 's/^Agent: *\([^ ]*\).*/\1/p' "$BRIEF" | head -1)
  ROLE=$(sed -n 's/^Role: *//p' "$BRIEF" | head -1)
  SURFACES=$(sed -n 's/^Surfaces: *//p' "$BRIEF" | head -1)
  printf '%s' "$AGENT" | grep -qE '^[a-z][a-z0-9]*(-[a-z0-9]+)*$' \
    || { echo "run.sh: 'Agent:' in $BRIEF must be a kebab-case name (e.g. reading-list), got '${AGENT}'" >&2; exit 2; }
  [ -n "$ROLE" ] || { echo "run.sh: $BRIEF needs a 'Role:' line for the agent registry" >&2; exit 2; }

  BRIEF_ID=$(basename "$BRIEF" .md)
  RUN_ID=${FACTORY_RUN_ID:-$BRIEF_ID}
  RUN="factory/runs/$RUN_ID"
  BRANCH="factory/$RUN_ID"
  STATE="$RUN/state"
  DIR="agents/$AGENT"
  FEATURE="specs/features/$AGENT"
  BACKEND=${FACTORY_BACKEND:-claude}
  MAX_TURNS=${FACTORY_MAX_TURNS:-60}
  STAGE_TIMEOUT=${FACTORY_STAGE_TIMEOUT:-1800}
  MAX_COST=${FACTORY_MAX_COST_USD:-15.00}
  PR_MODE=${FACTORY_PR:-file}
  BASE=${FACTORY_BASE:-main}
  RETRIES=${FACTORY_RETRIES:-3}
  PASSES=${FACTORY_IMPLEMENT_PASSES:-8}
  REVIEW_ROUNDS=${FACTORY_REVIEW_ROUNDS:-2}
  STAGE_NOTE=""
  RETRY_WAIT=${FACTORY_RETRY_WAIT:-65}
  ATTEMPT=0
  CURRENT_STAGE=start

  if ! git diff --quiet HEAD || ! git diff --cached --quiet; then
    echo "run.sh: tracked files have uncommitted changes; commit or stash them first." >&2
    exit 2
  fi
  if ! git show-ref --verify --quiet "refs/heads/$BRANCH" && [ -e "$DIR" ]; then
    echo "run.sh: $DIR already exists; a factory creates new agents only." >&2
    exit 2
  fi

  mkdir -p "$RUN"
  ORIG=$(git rev-parse --abbrev-ref HEAD)
  # The repository holds unrelated untracked work. Gates and cleanup only ever
  # act on files that appear after this point.
  git ls-files --others --exclude-standard > "$RUN/baseline"

  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git switch -q "$BRANCH" || exit 2
    log "resume run=$RUN_ID branch=$BRANCH backend=$BACKEND"
  else
    git switch -q -c "$BRANCH" "$BASE" || exit 2
    log "start run=$RUN_ID brief=$BRIEF agent=$AGENT branch=$BRANCH backend=$BACKEND"
  fi
  trap 'on_interrupt' INT TERM

  stage_spec
  stage_scaffold
  stage_test
  gate_red
  stage_implement
  stage_register
  stage_review
  stage_pr

  log "DONE run=$RUN_ID total_cost_usd=$(total_cost)"
  git switch -q "$ORIG"
}

# --------------------------------------------------------------------------- #
# Bookkeeping
# --------------------------------------------------------------------------- #

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$RUN/log"; }

is_done() { grep -q "^$1 " "$STATE" 2>/dev/null; }

mark_done() { echo "$1 $(git rev-parse --short HEAD) $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$STATE"; }

skip_if_done() {
  if is_done "$1"; then log "skip $1 (done in an earlier run)"; return 0; fi
  CURRENT_STAGE=$1
  return 1
}

total_cost() { awk '{s += $1} END {printf "%.4f", s + 0}' "$RUN/costs" 2>/dev/null || echo 0; }

# Files changed since the last commit, minus the untracked files that were
# already there when the run started.
changed_files() {
  { git diff --name-only --no-renames HEAD
    git ls-files --others --exclude-standard | grep -vxF -f "$RUN/baseline"
  } | sed '/^$/d' | sort -u
}

outside() {  # $1 prefix: changed files not under it
  changed_files | grep -v "^$1" || true
}

# Uncommitted agent work from a stage that did not pass is kept as a patch in
# the run directory and removed from the branch, so a rerun starts that stage
# clean. Only files this run changed are touched; the user's own are not.
set_aside_uncommitted() {
  local files f
  files=$(changed_files)
  if [ -n "$files" ]; then
    while IFS= read -r f; do git add -A -- "$f"; done <<< "$files"
    git diff --cached > "$RUN/rejected-$CURRENT_STAGE.patch"
    git reset -q --hard HEAD
    log "set aside uncommitted changes from $CURRENT_STAGE in $RUN/rejected-$CURRENT_STAGE.patch"
  fi
}

stop() {  # $1 stage, $2 reason, $3 decision a person must make
  log "STOP $1: $2"
  set_aside_uncommitted
  {
    echo "# STOP $(date -u +%Y-%m-%dT%H:%M:%SZ) run=$RUN_ID stage=$1"
    echo
    echo "**Reason:** $2"
    echo
    echo "**Completed stages:**"
    if [ -s "$STATE" ]; then sed 's/^\([^ ]*\) \([^ ]*\) \(.*\)$/- \1 at commit \2 (\3)/' "$STATE"; else echo "- none"; fi
    echo
    echo "**Decision needed:** $3"
    echo
    echo "Branch \`$BRANCH\`, log \`$RUN/log\`, cost so far \$$(total_cost)."
  } > "$RUN/stop.md"
  git switch -q "$ORIG" 2>/dev/null
  exit 1
}

on_interrupt() {
  log "interrupted during $CURRENT_STAGE"
  set_aside_uncommitted
  git switch -q "$ORIG" 2>/dev/null
  log "rerun the same command to continue from $CURRENT_STAGE"
  exit 130
}

with_timeout() {  # portable: GNU timeout, Homebrew gtimeout, or perl's alarm
  if command -v timeout >/dev/null 2>&1; then timeout "$STAGE_TIMEOUT" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then gtimeout "$STAGE_TIMEOUT" "$@"
  else perl -e 'alarm shift; exec @ARGV' "$STAGE_TIMEOUT" "$@"
  fi
}

json_field() {  # $1 file, $2 field: print a top-level field of a JSON object
  python3 -c 'import json,sys
try: v = json.load(open(sys.argv[1])).get(sys.argv[2], "")
except Exception: v = ""
print("" if v is None else v)' "$1" "$2"
}

run_check() { bash factory/check.sh "$AGENT" > "$1" 2>&1; }

# --------------------------------------------------------------------------- #
# Running one headless agent
# --------------------------------------------------------------------------- #

# A provider's rate limit is not the stage's fault: wait and run the stage again,
# up to FACTORY_RETRIES times, from a clean tree (partial work is kept as a patch).
run_stage() {
  local attempt=0 rc
  while :; do
    ATTEMPT=$attempt
    run_stage_once "$@"; rc=$?
    [ "$rc" -eq 75 ] || return "$rc"
    attempt=$((attempt + 1))
  done
}

rate_limited() {  # $1 agent output: does it look like a provider rate limit?
  python3 -c 'import json,re,sys
try: d = json.load(open(sys.argv[1]))
except Exception: sys.exit(1)
text = str(d.get("result") or "")
sys.exit(0 if d.get("is_error") and re.search(r"rate.?limit|tokens per minute|too many (requests|tokens)|429|quota|overloaded", text, re.I) else 1)' "$1"
}

run_stage_once() {  # $1 stage, $2 allowed tools (claude), $3 read|write (codex sandbox)
  local stage=$1 tools=$2 access=$3 out="$RUN/$1.out.json" rc start remaining prompt model_args=()
  remaining=$(awk -v max="$MAX_COST" -v used="$(total_cost)" 'BEGIN {printf "%.4f", max - used}')
  if awk -v r="$remaining" 'BEGIN {exit !(r <= 0)}'; then
    stop "$stage" "run budget of \$$MAX_COST is used up" "Raise FACTORY_MAX_COST_USD for this run, or split the brief."
  fi
  prompt="$(cat "factory/prompts/$stage.md")

Issue file: $BRIEF
Run directory: $RUN
Agent folder: $DIR
Feature folder: $FEATURE${STAGE_NOTE:+

$STAGE_NOTE}"
  start=$(date +%s)
  [ -n "${FACTORY_MODEL:-}" ] && model_args=(--model "$FACTORY_MODEL")

  case "$BACKEND" in
    claude)
      # --setting-sources project and --strict-mcp-config keep personal hooks,
      # settings and MCP servers out of the run: only this repo's settings apply.
      with_timeout claude -p "$prompt" \
        --allowedTools "$tools" \
        --output-format json \
        --max-turns "$MAX_TURNS" \
        --max-budget-usd "$remaining" \
        --setting-sources project \
        --strict-mcp-config \
        ${model_args[@]+"${model_args[@]}"} \
        < /dev/null > "$out" 2> "$RUN/$stage.err"
      rc=$?
      ;;
    codex)
      # Codex has no per-tool allowlist; the sandbox is its permission boundary.
      local sandbox=workspace-write
      [ "$access" = read ] && sandbox=read-only
      with_timeout codex exec --sandbox "$sandbox" --ephemeral -o "$RUN/$stage.txt" "$prompt" \
        < /dev/null > "$RUN/$stage.jsonl" 2> "$RUN/$stage.err"
      rc=$?
      python3 -c 'import json,sys,pathlib
p = pathlib.Path(sys.argv[1]); rc = int(sys.argv[2])
text = p.read_text() if p.exists() else ""
json.dump({"subtype": "success" if rc == 0 else "error", "is_error": rc != 0, "result": text,
           "num_turns": None, "total_cost_usd": None}, open(sys.argv[3], "w"))' "$RUN/$stage.txt" "$rc" "$out"
      ;;
    opencode)
      # opencode has no per-tool flag: the permission config is its boundary, built
      # per stage from the same tool list. An empty XDG_CONFIG_HOME keeps your
      # personal config and MCP servers out of the run; --pure drops plugins.
      # It has no turn or budget cap, so only the stage timeout bounds a stage.
      local ocfg="$RUN/.opencode-config" ocmodel=()
      mkdir -p "$ocfg"
      [ -n "${FACTORY_MODEL:-}" ] && ocmodel=(-m "$FACTORY_MODEL")
      XDG_CONFIG_HOME="$ocfg" OPENCODE_CONFIG_CONTENT="$(python3 factory/opencode_permissions.py "$tools")" \
        with_timeout opencode run --pure --format json ${ocmodel[@]+"${ocmodel[@]}"} "$prompt" \
        < /dev/null > "$RUN/$stage.jsonl" 2> "$RUN/$stage.err"
      rc=$?
      python3 factory/opencode_result.py "$rc" "${FACTORY_MODEL:-default}" < "$RUN/$stage.jsonl" > "$out"
      ;;
    fake)
      FACTORY_STAGE=$stage FACTORY_RUN=$RUN with_timeout python3 "$FACTORY_FAKE_AGENT" "$prompt" < /dev/null > "$out" 2> "$RUN/$stage.err"
      rc=$?
      ;;
    *)
      stop "$stage" "unknown FACTORY_BACKEND=$BACKEND" "Use claude, codex or opencode."
      ;;
  esac

  local secs=$(( $(date +%s) - start ))
  if [ "$rc" -eq 124 ] || [ "$rc" -eq 142 ]; then
    stop "$stage" "agent timed out after ${STAGE_TIMEOUT}s" "Look at $out and $RUN/$stage.err; raise FACTORY_STAGE_TIMEOUT or simplify the brief."
  fi
  local subtype turns cost is_error model tokens
  subtype=$(json_field "$out" subtype)
  model=$(python3 -c 'import json,sys
try: print(",".join(json.load(open(sys.argv[1])).get("modelUsage", {})) or "n/a")
except Exception: print("n/a")' "$out")
  turns=$(json_field "$out" num_turns)
  cost=$(json_field "$out" total_cost_usd)
  is_error=$(json_field "$out" is_error)
  tokens=$(json_field "$out" total_tokens)
  [ -n "$cost" ] && echo "$cost" >> "$RUN/costs"
  log "stage=$stage exit=$rc subtype=${subtype:-?} model=$model turns=${turns:-n/a} cost_usd=${cost:-n/a}${tokens:+ tokens=$tokens} seconds=$secs"
  if [ "$rc" -ne 0 ] || [ "$is_error" = "True" ] || [ "$subtype" != "success" ]; then
    if rate_limited "$out"; then
      if [ "$ATTEMPT" -lt "$RETRIES" ]; then
        log "stage=$stage rate limited by the provider; waiting ${RETRY_WAIT}s, retry $((ATTEMPT + 1))/$RETRIES"
        set_aside_uncommitted
        sleep "$RETRY_WAIT"
        return 75
      fi
      stop "$stage" "the provider's rate limit persisted through $RETRIES retries" \
        "Wait, use another model (FACTORY_MODEL) or a higher quota, then rerun the same command."
    fi
    stop "$stage" "agent ended with ${subtype:-exit $rc}" "Read $out and $RUN/$stage.err, then rerun to retry this stage."
  fi
}

# --------------------------------------------------------------------------- #
# Stages and gates
# --------------------------------------------------------------------------- #

test_lines() { sed -n "s#^Test: \($DIR/tests/[A-Za-z0-9_]*\.py\)::\(test_[A-Za-z0-9_]*\).*#\1 \2#p" "$RUN/spec.md"; }

stage_spec() {
  skip_if_done spec && return
  run_stage spec "Read,Grep,Glob,Write" write
  local spec="$RUN/spec.md" doc stray
  [ -s "$spec" ] || stop spec "spec.md is missing" "Read $RUN/spec.out.json: did the agent misread the prompt or the brief?"
  if grep -q '^BLOCKED:' "$spec"; then
    stop spec "the spec stage could not proceed: $(grep '^BLOCKED:' "$spec" | head -1)" "Answer the question in the brief and rerun on a new run id."
  fi
  grep -qE '^1\. ' "$spec" || stop spec "spec.md has no numbered acceptance criteria" "Sharpen the brief."
  [ -n "$(test_lines)" ] || stop spec "spec.md names no test as 'Test: $DIR/tests/<file>.py::<test_name>'" "Check prompts/spec.md and rerun."
  stray=$(outside "$FEATURE/")
  [ -z "$stray" ] || stop spec "the spec stage changed files outside $FEATURE/: $(echo $stray)" "Tighten the spec stage's permissions or prompt."
  for doc in task_spec technical_spec test_plan; do
    [ -s "$FEATURE/$doc.md" ] || stop spec "$FEATURE/$doc.md is missing" "Every feature needs its three documents (see AGENTS.md); check prompts/spec.md."
  done
  git add -A -- "$FEATURE"
  git commit -q -m "factory($RUN_ID): specs for $AGENT" || stop spec "commit failed" "Check git status on $BRANCH."
  mark_done spec
}

stage_scaffold() {
  skip_if_done scaffold && return
  # The copy command from agents/README.md, run by the script rather than by a model.
  [ ! -e "$DIR" ] || stop scaffold "$DIR already exists" "Pick another agent name in the brief."
  mkdir -p "$DIR"
  rsync -a \
    --exclude '/memory/data/*' \
    --exclude '.env' --exclude '.env.local' --exclude '.venv/' \
    --exclude '__pycache__/' --exclude '*.pyc' --exclude '.pytest_cache/' \
    --exclude '/tests/' --exclude '/evals/' \
    agents/example-agent/ "$DIR/" || stop scaffold "rsync from agents/example-agent failed" "Check that agents/example-agent exists."
  # Everything mechanical is done here, so no model has to read the reference to do it:
  # module prefix, settings prefix, names, and env loading confined to the agent folder.
  python3 - "$DIR" "$AGENT" <<'PY' || stop scaffold "renaming the copy failed" "Check $DIR and agents/example-agent."
import pathlib, re, sys
root, slug = pathlib.Path(sys.argv[1]), sys.argv[2]
snake, env, title = slug.replace("-", "_"), slug.replace("-", "_").upper(), slug.replace("-", " ").title()
for path in sorted(root.rglob("*")):
    if not path.is_file() or "__pycache__" in path.parts:
        continue
    try:
        text = path.read_text()
    except UnicodeDecodeError:
        continue
    text = (text.replace("Example Agent", title).replace("EXAMPLE_AGENT", env).replace("example-agent", slug)
            .replace("example_agent", snake).replace("example_", snake + "_"))
    if path.name == "agent_env.py":
        text = text.replace("reversed([AGENT_DIR, *AGENT_DIR.parents])", "[AGENT_DIR]")
        text = re.sub(r'""".*?"""', '"""Load .env / .env.local from the agent folder only.\n\n    Directories above it are never read, so the repository\'s own credentials cannot leak in.\n    """', text, count=1, flags=re.S)
    path.write_text(text)
    if path.name == "example_agent.py":   # the CLI entry point is <snake>.py, as the text now says
        path.rename(path.with_name(snake + ".py"))
    elif path.name.startswith("example_"):
        path.rename(path.with_name(snake + "_" + path.name[len("example_"):]))
PY
  mkdir -p "$DIR/memory/data" "$DIR/tests"
  touch "$DIR/memory/data/.gitkeep"
  git add -A -f -- "$DIR/memory/data/.gitkeep"
  git add -A -- "$DIR"
  git commit -q -m "factory($RUN_ID): scaffold $AGENT from example-agent" || stop scaffold "commit failed" "Check git status on $BRANCH."
  mark_done scaffold
}

stage_test() {
  skip_if_done test && return
  run_stage test "Read,Grep,Glob,Edit,Write" write
  local files stray file name
  files=$(changed_files)
  [ -n "$files" ] || stop test "the test stage changed nothing" "Read $RUN/test.out.json."
  stray=$(outside "$DIR/tests/")
  [ -z "$stray" ] || stop test "the test stage changed files outside $DIR/tests/: $(echo $stray)" "Tighten prompts/test.md; only new test files may appear here."
  [ -z "$(git diff --name-only HEAD)" ] || stop test "the test stage modified existing files" "Tests are added, never edited."
  while read -r file name; do
    grep -qE "^ *(async )?def $name\(" "$file" 2>/dev/null \
      || stop test "the spec's test $name is not defined in $file" "Rerun; the name links the test to its spec."
  done <<< "$(test_lines)"
  git add -A -- "$DIR/tests"
  git commit -q -m "factory($RUN_ID): tests for $AGENT" || stop test "commit failed" "Check git status on $BRANCH."
  mark_done test
}

gate_red() {
  skip_if_done red && return
  local file name named=0
  if run_check "$RUN/red.txt"; then
    stop red-gate "the new tests passed before implementation" \
      "Close the brief if the behaviour already exists, or sharpen it so a test can fail."
  fi
  while read -r file name; do
    grep -q "$(basename "$file")" "$RUN/red.txt" && named=1
  done <<< "$(test_lines)"
  [ "$named" -eq 1 ] || stop red-gate "the suite fails, but not in the new tests" "See $RUN/red.txt; fix the environment (FACTORY_PYTHON) or the scaffold first."
  log "RED gate: the new tests fail as expected"
  mark_done red
}

stage_implement() {
  skip_if_done implement && return
  implement_loop ""
  gate_hygiene
  git add -A -- "$DIR"
  git commit -q -m "factory($RUN_ID): implement $AGENT" || stop implement "commit failed" "Check git status on $BRANCH."
  mark_done implement
}

# Runs implement passes until the suite is green. A weaker model can end its turn
# with a plan and no edits, or leave the suite red; each pass after the first is
# told what is still failing. $1: an optional note for the first pass (review findings).
implement_loop() {
  local first_note=$1 allow_noop=${2:-0} pass=1 files forbidden focus
  while :; do
    STAGE_NOTE=$first_note
    if [ "$pass" -gt 1 ]; then
      focus=$(grep -oE "$DIR/tests/[A-Za-z0-9_]+\.py" "$RUN/green.txt" 2>/dev/null | head -1)
      STAGE_NOTE="Pass $pass of $PASSES. Earlier passes left the suite failing; their edits are still in the working tree. Do not re-read everything: make the edits now.${focus:+
Focus this pass on: $focus (ignore the other failing tests until it passes).}
Failing output (tail):
$(tail -40 "$RUN/green.txt" 2>/dev/null)"
    fi
    run_stage implement "Read,Grep,Glob,Edit,Write,Bash(bash factory/check.sh:*),Bash(git mv:*),Bash(git rm:*)" write
    STAGE_NOTE=""
    files=$(changed_files)
    # Allowed: files under agents/<slug>/ except its tests. Everything else is out of bounds.
    forbidden=$( { printf '%s\n' "$files" | grep -v "^$DIR/"; printf '%s\n' "$files" | grep "^$DIR/tests/"; } | sed '/^$/d' )
    [ -z "$forbidden" ] || stop implement "the implementer touched files it may not change: $(echo $forbidden)" \
      "Tests, factory/ and other agents are off limits to the implement stage. Rerun; if it repeats, tighten prompts/implement.md."
    if run_check "$RUN/green.txt" && { [ -n "$files" ] || [ "$allow_noop" = 1 ]; }; then break; fi
    [ -n "$files" ] || echo "NOTE: that pass changed no files; start editing immediately." >> "$RUN/green.txt"
    if [ "$pass" -ge "$PASSES" ]; then
      [ -n "$files" ] || stop implement "the implement stage changed nothing (after $pass pass(es))" "Read $RUN/implement.out.json; try a stronger FACTORY_MODEL or a smaller brief."
      stop green-gate "the suite fails after implementation ($pass pass(es))" "See $RUN/green.txt. Rerun to retry the implement stage."
    fi
    log "implement pass $pass/$PASSES left the suite failing; running another pass with the failing output"
    first_note=""
    pass=$((pass + 1))
  done
  log "GREEN gate: suite passes"
}

# agents/AGENTS.md "Naming and local safety" and "Build a new agent", as checks.
gate_hygiene() {
  local hits missing=() word
  # Identifiers must be renamed everywhere. The path `example-agent` is only a leftover
  # in code: prose such as "Built from ../example-agent/" is honest provenance.
  hits=$( { grep -rIlE 'example_agent|EXAMPLE_AGENT|\bexample_(core|service|chat)\b' "$DIR" --exclude-dir=__pycache__
            grep -rIl 'example-agent' "$DIR" --exclude-dir=__pycache__ --exclude='*.md'; } | sort -u || true)
  [ -z "$hits" ] || stop hygiene-gate "reference-agent names (example_agent / EXAMPLE_AGENT / example_core / example-agent in code) are left in: $(echo $hits)" \
    "Rename them to the new agent's names; the copy must not read as the example."
  if [ -f "$DIR/agent_env.py" ] && grep -q 'parents' "$DIR/agent_env.py"; then
    stop hygiene-gate "$DIR/agent_env.py loads .env files from parent directories" \
      "Load only the agent folder's own .env/.env.local, so the repository root's credentials cannot leak in."
  fi
  hits=$(grep -rIl '0\.0\.0\.0' "$DIR" --exclude-dir=__pycache__ --exclude-dir=tests || true)
  [ -z "$hits" ] || stop hygiene-gate "a server binds to 0.0.0.0 in: $(echo $hits)" "API and UI bind to 127.0.0.1; network access needs its own design."
  hits=$(find "$DIR" \( -name '.env' -o -name '.env.local' -o -name '.venv' \) -not -path '*/__pycache__/*'; \
         find "$DIR/memory/data" -type f ! -name .gitkeep 2>/dev/null)
  [ -z "$hits" ] || stop hygiene-gate "secrets, a virtualenv or live memory data are present: $(echo $hits)" "Remove them; keep local state out of the agent folder."
  for word in purpose offline retention; do
    grep -qi "$word" "$DIR/README.md" 2>/dev/null || missing+=("$word")
  done
  [ ${#missing[@]} -eq 0 ] || stop hygiene-gate "$DIR/README.md does not state: ${missing[*]}" \
    "The README must hold the agent's contract: purpose, offline behavior and memory retention."
  log "hygiene gate: pass"
}

stage_register() {
  skip_if_done register && return
  python3 - "$AGENT" "$ROLE" <<'PY' || stop register "could not add the agent to agents/AGENTS.md" "Add the registry row by hand."
import re, sys
slug, role = sys.argv[1:3]
path = "agents/AGENTS.md"
lines = open(path).read().split("\n")
row = f"| [`{slug}/`]({slug}/) | {role} | Factory draft; pending human review |"
if not any(l.startswith(f"| [`{slug}/`]") for l in lines):
    last = max(i for i, l in enumerate(lines) if re.match(r"\| \[`[^`]+/`\]", l))
    lines.insert(last + 1, row)
    open(path, "w").write("\n".join(lines))
PY
  git add -- agents/AGENTS.md
  git commit -q -m "factory($RUN_ID): register $AGENT" || stop register "commit failed" "Check git status on $BRANCH."
  mark_done register
}

stage_review() {
  skip_if_done review && return
  local round=0 findings
  while :; do
    review_once
    [ "$(json_field "$RUN/review.json" verdict)" = approve ] && break
    findings=$(python3 -c 'import json,sys; print("\n".join("- " + f for f in json.load(open(sys.argv[1]))["findings"]))' "$RUN/review.json")
    if [ "$round" -ge "$REVIEW_ROUNDS" ]; then
      stop verdict-gate "the reviewer asked for changes: $(echo "$findings" | tr '\n' ' ')" \
        "Decide whether the findings are right. If so, fix them on $BRANCH by hand or rerun with FACTORY_REVIEW_ROUNDS higher."
    fi
    round=$((round + 1))
    log "review round $round/$REVIEW_ROUNDS: the reviewer asked for changes; fixing them"
    CURRENT_STAGE=test
    test_round "$round" "$findings"
    CURRENT_STAGE=implement
    implement_loop "Review round $round of $REVIEW_ROUNDS. An independent reviewer read the change and asked for these fixes. Make the ones about the code (existing tests stay frozen; new tests were just added for findings about tests), then run the check:
$findings" 1
    gate_hygiene
    git add -A -- "$DIR"
    git diff --cached --quiet || git commit -q -m "factory($RUN_ID): address review round $round" || stop review "commit failed" "Check git status on $BRANCH."
    CURRENT_STAGE=review
  done
  log "verdict gate: approve"
  mark_done review
}

# A review round may add tests for findings about missing or weak tests, but never
# edit or delete an existing test line: a weakened test is how a bad change passes.
test_round() {  # $1 round, $2 findings
  STAGE_NOTE="Review round $1. An independent reviewer asked for these changes. Add tests only for the findings about tests (missing regression tests, weak assertions: add a stricter new test beside the weak one). Do not edit or delete any existing test line. If no finding concerns tests, change nothing:
$2"
  run_stage test "Read,Grep,Glob,Edit,Write" write
  STAGE_NOTE=""
  [ -n "$(changed_files)" ] || return 0
  local stray; stray=$(outside "$DIR/tests/")
  [ -z "$stray" ] || stop test "the review-round test stage changed files outside $DIR/tests/: $(echo $stray)" "Only new tests may be added in a review round."
  if git diff HEAD -U0 -- "$DIR/tests" | grep -E '^-' | grep -vqE '^--- '; then
    stop test "the review-round test stage edited or deleted existing test lines" "Existing tests are frozen; strengthen by adding new ones."
  fi
  git add -A -- "$DIR/tests"
  git commit -q -m "factory($RUN_ID): tests for review round $1" || stop test "commit failed" "Check git status on $BRANCH."
}

review_once() {
  git diff "$BASE"...HEAD -- . ':!factory' > "$RUN/diff.patch"
  run_stage review "Read,Grep,Glob" read
  # The reviewer stays read-only: it answers with JSON, and this script checks and saves it.
  if ! python3 -c 'import json,re,sys
result = json.load(open(sys.argv[1])).get("result") or ""
open(sys.argv[2], "w").write(result)
match = re.search(r"\{.*\}", result, re.S)
try: data = json.loads(match.group(0)) if match else None
except json.JSONDecodeError: data = None
ok = isinstance(data, dict) and data.get("verdict") in ("approve", "changes") and isinstance(data.get("findings"), list)
if not ok: sys.exit(1)
json.dump({"verdict": data["verdict"], "findings": data["findings"]}, open(sys.argv[3], "w"), indent=2)' \
    "$RUN/review.out.json" "$RUN/review.txt" "$RUN/review.json"; then
    stop review "the reviewer returned no valid verdict" "Read $RUN/review.txt. Rerun to retry the review."
  fi
}

stage_pr() {
  skip_if_done pr && return
  local title body="$RUN/pr.md"
  title="Add $AGENT agent ($(head -1 "$BRIEF" | sed 's/^# *//'))"
  {
    echo "Factory run \`$RUN_ID\` for \`$BRIEF\`. **Draft: a person decides whether to merge.**"
    echo
    echo "## Acceptance criteria"
    sed -n '/^1\. /,/^$/p' "$RUN/spec.md"
    echo
    echo "## Evidence"
    echo "- RED: the new tests failed before implementation ($RUN/red.txt)"
    echo "- GREEN: offline suite → $(tail -1 "$RUN/green.txt")"
    echo "- Review: approve$(python3 -c 'import json,sys; f=json.load(open(sys.argv[1]))["findings"]; print(", findings: " + "; ".join(f) if f else ", no findings")' "$RUN/review.json")"
    echo "- Cost: \$$(total_cost) across all stages"
    echo
    echo "## Needs a person (the factory cannot do these)"
    echo "- Real-browser check of the UI and chat if the agent has one (surfaces: ${SURFACES:-not stated}); \`agents/AGENTS.md\` requires it before acceptance."
    echo "- A CLI/tool/API walk-through with isolated data and, if wanted, a real provider key."
    echo "- Editorial and product judgement of the agent's behavior; registry status is \"Factory draft\"."
    echo
    echo "Log and stage outputs: \`$RUN/\`."
  } > "$body"

  if [ "$PR_MODE" = gh ]; then
    local url
    git push -q -u origin "$BRANCH" || stop pr "git push failed" "Check the remote and your credentials."
    url=$(gh pr list --head "$BRANCH" --state open --json url -q '.[0].url' 2>/dev/null)
    if [ -n "$url" ]; then
      log "PR already open for $BRANCH: $url"
    else
      url=$(gh pr create --draft --base "$BASE" --head "$BRANCH" --title "$title" --body-file "$body") \
        || stop pr "gh pr create failed" "Open the PR by hand from $body."
      log "draft PR opened: $url"
    fi
    echo "$url" > "$RUN/pr_url"
  else
    log "wrote $body (FACTORY_PR=gh opens a draft PR instead)"
  fi
  mark_done pr
}

main "$@"
