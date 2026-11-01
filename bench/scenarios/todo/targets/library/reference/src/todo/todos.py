import re
from dataclasses import asdict, dataclass
from datetime import date
from itertools import count

MAX_TITLE = 200
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class InvalidTodo(ValueError):
    pass


class UnknownTodo(KeyError):
    pass


@dataclass
class Todo:
    id: int
    title: str
    done: bool = False
    due: str | None = None


@dataclass
class ListedTodo(Todo):
    position: int = 0


def numbered(todos: list[Todo]) -> list[ListedTodo]:
    return [ListedTodo(**asdict(todo), position=n) for n, todo in enumerate(todos, 1)]


def clean_title(raw: str) -> str:
    title = raw.strip()
    if not 1 <= len(title) <= MAX_TITLE:
        raise InvalidTodo(f"a title needs 1 to {MAX_TITLE} characters")
    return title


def clean_due(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        if not ISO_DATE.match(raw):
            raise ValueError
        return date.fromisoformat(raw).isoformat()
    except ValueError as error:
        raise InvalidTodo(f"'{raw}' is not a date in YYYY-MM-DD form") from error


class TodoList:
    def __init__(self):
        self.ids = count(1)
        self.todos: list[Todo] = []

    def add(self, title: str, due: str | None = None) -> Todo:
        todo = Todo(0, clean_title(title), due=clean_due(due))
        todo.id = next(self.ids)
        self.todos.append(todo)
        return todo

    def ordered(self) -> list[Todo]:
        return sorted(self.todos, key=lambda t: (t.due is None, t.due or ""))

    def remaining(self) -> list[ListedTodo]:
        return numbered([t for t in self.ordered() if not t.done])

    def list(self) -> list[ListedTodo]:
        return numbered(self.ordered())

    def find(self, id_: int) -> Todo:
        for todo in self.todos:
            if todo.id == id_:
                return todo
        raise UnknownTodo(id_)

    def complete(self, id_: int) -> Todo:
        todo = self.find(id_)
        todo.done = True
        return todo

    def delete(self, id_: int) -> None:
        self.todos.remove(self.find(id_))

    def clear_completed(self) -> int:
        before = len(self.todos)
        self.todos = [t for t in self.todos if not t.done]
        return before - len(self.todos)
