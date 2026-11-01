import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from todo import TodoList


class TodoListTest(unittest.TestCase):
    def test_dated_first(self):
        todos = TodoList()
        todos.add("later")
        todos.add("soon", "2026-01-02")
        self.assertEqual([t.title for t in todos.list()], ["soon", "later"])

    def test_errors(self):
        todos = TodoList()
        with self.assertRaises(ValueError):
            todos.add("")
        with self.assertRaises(KeyError):
            todos.complete(9)
