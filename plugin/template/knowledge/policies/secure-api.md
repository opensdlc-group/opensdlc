---
kind: policy
owner: @YOUR-ORG/security
review-by: 2027-04-30
description: Apply the API security standard whenever creating or changing an external-facing endpoint, reviewing API code, or writing an OpenAPI spec
tags: api, auth
paths: src/api/**, **/routes/**, **/openapi*.yaml
stages: spec, plan, build, review
skill: secure-api-review
---
# Secure API

An example policy. Replace it with your own, keep the frontmatter shape, and run `python3 -m opensdlc skills`.

## Rules

1. **Authentication**: every endpoint requires the gateway token. No anonymous routes outside `/health`.
2. **Input validation**: validate request bodies against the OpenAPI schema and reject unknown fields.
3. **Audit**: every state-changing endpoint emits an audit event with actor, action, entity and timestamp.
4. **Data classification**: fields tagged `pii` in the schema never appear in logs or error messages.

## How to check

Run the API contract tests and include their output in your summary.
