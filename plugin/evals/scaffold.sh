# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

set -euo pipefail

EVALS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FIXTURES="$EVALS/fixtures"
TEMPLATE="$(dirname "$EVALS")/template"

opensdlc() {
  PYTHONPATH=.opensdlc/cli python3 -P -m opensdlc "$@" >/dev/null
}

commit() {
  git add -A
  git -c user.name="OpenSDLC evals" -c user.email=evals@opensdlc.invalid commit -qm "$1"
}

repository() {
  cp -R "$TEMPLATE/." .
  rm -rf knowledge/policies/secure-api.md .claude/skills/secure-api-review
  cp -R "$FIXTURES/todo/." .
  chmod +x todo
  opensdlc skills
  git init -q -b main
  commit "Tickets 1 to 3"
}

ticket() {
  mkdir -p .opensdlc/out
  cp "$FIXTURES/tickets/$1.md" .opensdlc/out/ticket.md
}

accepted_intent() {
  mkdir -p "changes/$1"
  cp "$FIXTURES/intents/$1.md" "changes/$1/intent.md"
  opensdlc accept "$1" --kind intent
  commit "Accept intent for $1"
  opensdlc context "$1" --stage spec
}

drafted_spec() {
  accepted_intent "$1"
  cp "$FIXTURES/specs/$2.md" "changes/$1/spec.md"
  opensdlc pin "$1"
}

accepted_spec() {
  accepted_intent "$1"
  cp "$FIXTURES/specs/$2.md" "changes/$1/spec.md"
  opensdlc pin "$1"
  opensdlc accept "$1" --kind spec
  commit "Accept spec for $1"
  opensdlc context "$1" --stage plan
}

accepted_plan() {
  accepted_spec "$1" "$2"
  cp "$FIXTURES/plans/$3.md" "changes/$1/plan.md"
  opensdlc pin "$1"
  opensdlc accept "$1" --kind plan
  commit "Accept plan for $1"
  opensdlc context "$1" --stage build
}

built() {
  git apply "$FIXTURES/patches/$1.patch"
}

pull_request() {
  git checkout -q -b proposed
  git apply "$FIXTURES/patches/$1.patch"
  commit "$2"
  mkdir -p .opensdlc/out
  git diff main...proposed > .opensdlc/out/pr.diff
  printf 'Change: %s\n' "$3" > .opensdlc/out/pr-body.md
  python3 -c 'import json, subprocess, sys; files = subprocess.run(["git", "diff", "--name-only", "main...proposed"], capture_output=True, text=True).stdout.split(); print(json.dumps({"title": sys.argv[1], "body": open(".opensdlc/out/pr-body.md").read(), "files": files}))' "$2" > .opensdlc/out/pr.json
  printf '{"days": 90, "keys": {}}\n' > .opensdlc/out/review-history.json
  opensdlc review-context --base main --head HEAD --body-file .opensdlc/out/pr-body.md
}
