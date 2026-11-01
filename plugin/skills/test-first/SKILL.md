---
name: test-first
description: Builds behavior one failing test at a time at agreed seams. Use when implementing a slice of a plan, fixing a bug, or whenever behavior should be proven by tests written before the code.
---
# Test first, one slice at a time

## Where tests go

Test at seams: the public boundaries where behavior is observable without reaching inside. The spec's Testing Decisions name the seams; do not add tests anywhere else without agreeing it first. Fewer, higher seams beat many low ones.

## The loop

1. Write one test for the next piece of behavior, at a seam, named for the capability it proves.
2. Run it and watch it fail for the right reason.
3. Write the least code that makes it pass.
4. Run the file, then move to the next behavior. Run the full suite at the end of the slice.

Refactoring is a separate step after the slice is green, not part of the loop.

## What makes a test worth keeping

- It checks behavior through the public interface and survives an internal rewrite.
- Its expected values come from somewhere independent: a known-good literal, a worked example, the spec. A test that recomputes the answer the way the code does proves nothing.
- It mocks only at system boundaries (network, clock, third-party services), never internal collaborators.
- Writing all the tests first and then all the code tests imagined behavior. Go one test at a time so each test learns from the last.
