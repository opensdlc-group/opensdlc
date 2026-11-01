---
name: repro
description: Fixes a bug test-first: reproduces it as a failing test, freezes the tests with a hook-enforced lock, then changes only the code until the test passes. Use when asked to fix a bug, regression or incident whose behavior can be reproduced.
argument-hint: "[bug description or issue reference]"
---
# Reproduce, freeze, fix

Bug: $ARGUMENTS

1. If the cause is not obvious, use the `opensdlc:diagnose` skill to find and prove it before writing any test.
2. Write the failing test as the `opensdlc:test-first` skill describes, at the narrowest public seam that shows the bug.
3. Run it. Confirm it fails, and fails for the reason the bug describes. A test that fails for another reason proves nothing; fix the test until the failure is the bug.
4. Commit the test on its own with a message that names the bug.
5. Freeze the tests for the rest of this session by writing `.opensdlc/locks/tests.json`:

   ```json
   {"session": "${CLAUDE_SESSION_ID}", "reason": "<one line naming the bug>"}
   ```

   From here the OpenSDLC hooks block edits to every path in `tests` in `.opensdlc/config.json`, and to the lock itself. The freeze ends with the session.
6. Change the code until the new test and the full suite pass. If you become convinced the test itself is wrong, stop and say why. A human clears the freeze by starting a new session.
7. Report the failing output from step 3 and the passing output from step 6 together, so the reviewer sees the proof.
8. If this was an incident, run `/opensdlc:learn` afterwards to turn it into an eval case.
