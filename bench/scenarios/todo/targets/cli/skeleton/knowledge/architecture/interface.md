---
kind: architecture
owner: product-owner
review-by: 2027-12-31
always: true
---
# Command-line interface

The `todo` program at the repository root is the product. Scripts and people both use it, so this contract holds for every command.

- Todos live in the JSON file named by the `TODO_FILE` environment variable. Create it when it is missing. Every command reads it and writes it back.
- A successful command prints exactly one JSON value on stdout and exits 0.
- A todo prints as a JSON object with `id` (a string or an integer), `title` and `done`. Tickets add fields.
- Invalid input exits 2 and an unknown id exits 3. Either way, print a one-line message on stderr and change nothing.
