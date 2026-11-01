import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from todo_cli.store import InvalidInput, Store, UnknownTodo


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "todos.json"

    def test_round_trip_and_order(self):
        store = Store(self.path)
        store.add("later", None)
        store.add("soon", "2026-01-02")
        store.save()
        self.assertEqual([t.title for t in Store(self.path).ordered()], ["soon", "later"])

    def test_rejects_bad_input(self):
        store = Store(self.path)
        with self.assertRaises(InvalidInput):
            store.add(" ", None)
        with self.assertRaises(InvalidInput):
            store.add("x", "2026-02-30")
        with self.assertRaises(UnknownTodo):
            store.complete("9")
