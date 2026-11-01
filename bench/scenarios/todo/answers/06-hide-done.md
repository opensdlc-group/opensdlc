Both needs are real, so we keep both:

- The list itself doesn't change. It still shows every todo, finished ones included, in the same order as now.
- Add a second view that shows only the todos that aren't done, in the same order as the full list. Name it exactly as below for the kind of software you are building:
  - command line: `./todo list --remaining`, printing the same JSON as `./todo list`
  - HTTP API: `GET /todos?remaining=true`, answering 200 with the same JSON as `GET /todos`
  - library: `TodoList.remaining()`, returning the same kind of list as `TodoList.list()`
  - web app: a `remaining-only` checkbox; while it is ticked the list shows only todos that aren't done, and unticking it shows every todo again
- Nothing else changes.
