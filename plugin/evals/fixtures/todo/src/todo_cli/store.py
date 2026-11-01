import json
import os
import tempfile


class StoreError(Exception):
    pass


def load(path: str) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            store = json.load(f)
    except FileNotFoundError:
        return {"next_id": 1, "todos": []}
    except (OSError, ValueError) as e:
        raise StoreError(f"cannot read {path}: {e}") from e
    if (
        not isinstance(store, dict)
        or not isinstance(store.get("next_id"), int)
        or isinstance(store.get("next_id"), bool)
        or not isinstance(store.get("todos"), list)
    ):
        raise StoreError(f"cannot read {path}: unexpected contents")
    return store


def save(path: str, store: dict) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    try:
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".todo-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(store, f)
            os.replace(tmp, path)
        except BaseException:
            os.unlink(tmp)
            raise
    except OSError as e:
        raise StoreError(f"cannot write {path}: {e}") from e


class UnknownId(Exception):
    pass


def mark_done(store: dict, todo_id: int) -> tuple[dict, bool]:
    """Return the todo and whether it changed."""
    for todo in store["todos"]:
        if type(todo.get("id")) is int and todo["id"] == todo_id:
            changed = todo.get("done") is not True
            todo["done"] = True
            return todo, changed
    raise UnknownId(f"no todo with id {todo_id}")


def delete(store: dict, todo_id: int) -> int:
    """Remove the todo with this id. `next_id` stays, so the id is never reissued."""
    for index, todo in enumerate(store["todos"]):
        if type(todo.get("id")) is int and todo["id"] == todo_id:
            del store["todos"][index]
            return todo_id
    raise UnknownId(f"no todo with id {todo_id}")


def add(store: dict, title: str) -> dict:
    todo = {"id": store["next_id"], "title": title, "done": False}
    store["todos"].append(todo)
    store["next_id"] = todo["id"] + 1
    return todo
