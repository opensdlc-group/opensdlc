No: ids are never reused. People and scripts keep ids, and a reused id would quietly point at a different todo. That was settled when the list was first built.

What the reporter needs is a short number to read off the screen. Give each todo the list shows a `position`: 1 for the first, 2 for the next, and so on, worked out each time the list is shown. Ids stay exactly as they are.

- command line: every todo `./todo list` prints carries `"position"`
- HTTP API: every todo in `GET /todos` carries `"position"`
- library: every todo `TodoList.list()` returns has a `position` attribute
- web app: every todo in the list shows its position in a `todo-position` element

Positions only exist in the list. Nothing else changes.
