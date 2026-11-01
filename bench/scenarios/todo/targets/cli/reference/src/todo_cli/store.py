import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

MAX_TITLE = 200
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class InvalidInput(Exception):
    pass


class UnknownTodo(Exception):
    pass


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    due: str | None = None

    def as_json(self) -> dict:
        return asdict(self)


def clean_title(raw: str) -> str:
    title = raw.strip()
    if not 1 <= len(title) <= MAX_TITLE:
        raise InvalidInput(f"a title needs 1 to {MAX_TITLE} characters")
    return title


def clean_due(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        if not ISO_DATE.match(raw):
            raise ValueError
        return date.fromisoformat(raw).isoformat()
    except ValueError as error:
        raise InvalidInput(f"'{raw}' is not a date in YYYY-MM-DD form") from error


class Store:
    def __init__(self, path: Path):
        self.path = path
        data = json.loads(path.read_text()) if path.is_file() else {"next": 1, "todos": []}
        self.next_id = data["next"]
        self.todos = [Todo(**raw) for raw in data["todos"]]

    def save(self) -> None:
        self.path.write_text(json.dumps({"next": self.next_id, "todos": [t.as_json() for t in self.todos]}, ensure_ascii=False))

    def add(self, title: str, due: str | None) -> Todo:
        todo = Todo(self.next_id, clean_title(title), due=clean_due(due))
        self.next_id += 1
        self.todos.append(todo)
        return todo

    def ordered(self) -> list[Todo]:
        return sorted(self.todos, key=lambda t: (t.due is None, t.due or ""))

    def shown(self, remaining: bool) -> list[Todo]:
        return [t for t in self.ordered() if not (remaining and t.done)]

    def find(self, id_: str) -> Todo:
        for todo in self.todos:
            if str(todo.id) == id_:
                return todo
        raise UnknownTodo(f"no todo with id {id_}")

    def complete(self, id_: str) -> Todo:
        todo = self.find(id_)
        todo.done = True
        return todo

    def delete(self, id_: str) -> int:
        todo = self.find(id_)
        self.todos.remove(todo)
        return todo.id

    def clear(self) -> int:
        before = len(self.todos)
        self.todos = [t for t in self.todos if not t.done]
        return before - len(self.todos)
