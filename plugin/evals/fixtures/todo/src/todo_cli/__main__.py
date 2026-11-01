import json
import os
import sys

from todo_cli import ids, store, title


def refuse(message: str, status: int = 2) -> int:
    print(f"todo: {message}", file=sys.stderr)
    return status


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: todo <command>", file=sys.stderr)
        return 2
    command, args = argv[0], argv[1:]
    new_title = None
    todo_id = None
    if command == "list" and not args:
        pass
    elif command == "add":
        try:
            new_title = title.make(args)
        except title.TitleError as e:
            return refuse(str(e))
    elif command in ("done", "delete"):
        try:
            todo_id = ids.parse(command, args)
        except ids.IdError as e:
            return refuse(str(e))
    else:
        return refuse(f"unknown command or arguments: {' '.join(argv)}")

    path = os.environ.get("TODO_FILE")
    if not path:
        return refuse("TODO_FILE is not set")
    try:
        data = store.load(path)
        output = data["todos"]
        changed = True
        if new_title is not None:
            output = store.add(data, new_title)
        elif command == "delete":
            output = {"deleted": store.delete(data, todo_id)}
        elif todo_id is not None:
            output, changed = store.mark_done(data, todo_id)
        if changed:
            store.save(path, data)
    except store.UnknownId as e:
        return refuse(str(e), 3)
    except store.StoreError as e:
        return refuse(str(e), 1)
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
