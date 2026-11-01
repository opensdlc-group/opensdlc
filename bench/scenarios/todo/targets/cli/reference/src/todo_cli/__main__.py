import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path

from .store import InvalidInput, Store, UnknownTodo

INVALID, UNKNOWN = 2, 3

COMMANDS: dict[str, Callable[[Store, argparse.Namespace], object]] = {
    "add": lambda store, args: store.add(args.title, args.due).as_json(),
    "list": lambda store, args: [t.as_json() | {"position": n} for n, t in enumerate(store.shown(args.remaining), 1)],
    "done": lambda store, args: store.complete(args.id).as_json(),
    "delete": lambda store, args: {"deleted": store.delete(args.id)},
    "clear": lambda store, args: {"removed": store.clear()},
}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="todo")
    commands = root.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add")
    add.add_argument("title")
    add.add_argument("--due")
    commands.add_parser("list").add_argument("--remaining", action="store_true")
    commands.add_parser("done").add_argument("id")
    commands.add_parser("delete").add_argument("id")
    commands.add_parser("clear")
    return root


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: todo {add,list,done,delete,clear} ...", file=sys.stderr)
        return INVALID
    args = parser().parse_args(argv)
    store = Store(Path(os.environ.get("TODO_FILE", "todos.json")))
    try:
        result = COMMANDS[args.command](store, args)
    except InvalidInput as error:
        print(error, file=sys.stderr)
        return INVALID
    except UnknownTodo as error:
        print(error, file=sys.stderr)
        return UNKNOWN
    store.save()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
