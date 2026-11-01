---
kind: architecture
owner: product-owner
review-by: 2027-12-31
always: true
---
# Library interface

The `todo` package under `src/todo/` is the product. Other teams import it, so this contract holds for every release.

- `from todo import TodoList`. A `TodoList()` holds its todos in memory.
- Todos come back as objects with the attributes `id`, `title` and `done`. Tickets add attributes.
- Invalid input raises `ValueError` and an unknown id raises `KeyError` (subclasses are fine). Neither changes anything.
