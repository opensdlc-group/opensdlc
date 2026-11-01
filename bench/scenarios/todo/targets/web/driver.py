import re
import time

from opensdlc_bench.adapters.web import SETTLE, AdapterError, until

ITEM = '[data-testid="todo-item"]'


def number(text: str | None) -> int | None:
    found = re.search(r"\d+", text or "")
    return int(found.group()) if found else None


def todos(page) -> list[dict]:
    found = []
    for element in page.locator(ITEM).all():
        title = element.get_by_test_id("todo-title")
        due = element.get_by_test_id("todo-due")
        position = element.get_by_test_id("todo-position")
        found.append({
            "id": element.get_attribute("data-id"),
            "title": title.first.text_content() if title.count() else None,
            "done": element.get_attribute("data-done") == "true",
            "due": due.first.text_content().strip() if due.count() else None,
            "position": number(position.first.text_content()) if position.count() else None,
        })
    return found


def find(page, id_: object) -> dict | None:
    return next((t for t in todos(page) if t["id"] == str(id_)), None)


def error_shown(page) -> bool:
    error = page.get_by_test_id("error")
    return error.count() > 0 and error.first.is_visible()


def add(page, args: dict) -> dict:
    before = {t["id"] for t in todos(page)}
    page.get_by_test_id("new-todo-title").fill(args["title"])
    if "due" in args:
        page.get_by_test_id("new-todo-due").fill(args["due"])
    page.get_by_test_id("add-todo").click()
    started = time.monotonic()

    def outcome() -> dict | None:
        added = [t for t in todos(page) if t["id"] not in before]
        if added:
            return added[0]
        if error_shown(page) and time.monotonic() - started > SETTLE:
            return {"error": "invalid"}
        return None
    return until(outcome, "the todo or an error to appear")


def complete(page, args: dict) -> dict:
    todo = find(page, args["id"])
    if todo is None:
        return {"error": "not_found"}
    if not todo["done"]:
        page.locator(f'{ITEM}[data-id="{todo["id"]}"]').get_by_test_id("complete-todo").click()
    return until(lambda: (t := find(page, args["id"])) and t["done"] and t, "the todo to show as done")


def delete(page, args: dict) -> dict | None:
    todo = find(page, args["id"])
    if todo is None:
        return {"error": "not_found"}
    page.locator(f'{ITEM}[data-id="{todo["id"]}"]').get_by_test_id("delete-todo").click()
    until(lambda: find(page, args["id"]) is None, "the todo to disappear")
    return None


def clear(page, args: dict) -> dict:
    page.get_by_test_id("clear-completed").click()
    until(lambda: not any(t["done"] for t in todos(page)), "done todos to disappear")
    shown = until(lambda: page.get_by_test_id("cleared-count").count() and page.get_by_test_id("cleared-count").first.text_content(), "cleared-count")
    removed = number(shown)
    if removed is None:
        raise AdapterError(f"cleared-count shows no number: {shown!r}")
    return {"removed": removed}


def list_remaining(page, args: dict) -> list[dict]:
    everything = len(todos(page))
    toggle = page.get_by_test_id("remaining-only")
    toggle.check()
    until(lambda: not any(t["done"] for t in todos(page)), "only remaining todos to show")
    shown = todos(page)
    toggle.uncheck()
    until(lambda: len(todos(page)) == everything, "every todo to show again")
    return shown


OPS = {"add": add, "list": lambda page, args: todos(page), "complete": complete, "delete": delete, "clear": clear, "list_remaining": list_remaining}
