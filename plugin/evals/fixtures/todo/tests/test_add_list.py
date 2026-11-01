import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class AddList(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.store = Path(tmp.name) / "todo.json"

    def run_todo(self, *args, store="default"):
        env = {k: v for k, v in os.environ.items() if k != "TODO_FILE"}
        if store == "default":
            env["TODO_FILE"] = str(self.store)
        return subprocess.run(
            [str(ROOT / "todo"), *args], capture_output=True, text=True, env=env
        )

    def assert_refused(self, result, code=2):
        self.assertEqual(result.returncode, code)
        self.assertEqual(result.stdout, "")
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)

    def assert_refused_unchanged(self, *args):
        before = self.store.read_bytes() if self.store.exists() else None
        self.assert_refused(self.run_todo(*args))
        after = self.store.read_bytes() if self.store.exists() else None
        self.assertEqual(before, after)

    def listed(self):
        result = self.run_todo("list")
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)

    def test_1_list_on_a_missing_file_prints_empty_array(self):
        result = self.run_todo("list")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), [])

    def test_2_11_add_prints_the_todo_and_list_matches(self):
        result = self.run_todo("add", "Buy milk")
        self.assertEqual(result.returncode, 0)
        todo = json.loads(result.stdout)
        self.assertEqual(todo, {"id": 1, "title": "Buy milk", "done": False})
        self.assertEqual(self.listed(), [todo])

    def test_3_9_ids_count_up_in_order_and_stay_the_same(self):
        self.run_todo("add", "Buy milk")
        self.run_todo("add", "Walk dog")
        self.run_todo("add", "Call mum")
        expected = [(1, "Buy milk"), (2, "Walk dog"), (3, "Call mum")]
        for _ in range(2):
            got = [(t["id"], t["title"]) for t in self.listed()]
            self.assertEqual(got, expected)

    def test_4_surrounding_spaces_are_dropped(self):
        todo = json.loads(self.run_todo("add", "  Buy milk ").stdout)
        self.assertEqual(todo["title"], "Buy milk")

    def test_5_unquoted_words_are_joined(self):
        todo = json.loads(self.run_todo("add", "buy", "milk").stdout)
        self.assertEqual(todo["title"], "buy milk")

    def test_6_200_characters_saved_201_refused(self):
        ok = self.run_todo("add", "x" * 200)
        self.assertEqual(ok.returncode, 0)
        self.assertEqual(json.loads(ok.stdout)["title"], "x" * 200)
        self.assert_refused_unchanged("add", "x" * 201)

    def test_6_201_refused_leaves_no_file(self):
        self.assert_refused(self.run_todo("add", "x" * 201))
        self.assertFalse(self.store.exists())

    def test_7_limit_counts_after_dropping_the_ends(self):
        result = self.run_todo("add", "  " + "x" * 200 + "  ")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["title"], "x" * 200)

    def test_8_empty_titles_are_refused(self):
        self.assert_refused_unchanged("add", "")
        self.assert_refused_unchanged("add", "   ")
        self.assert_refused_unchanged("add")
        self.run_todo("add", "Buy milk")
        self.assert_refused_unchanged("add", " \n ")

    def test_10_id_comes_from_the_counter_not_the_list(self):
        todos = [
            {"id": 1, "title": "a", "done": False},
            {"id": 2, "title": "b", "done": False},
        ]
        self.store.write_text(json.dumps({"next_id": 5, "todos": todos}))
        first = json.loads(self.run_todo("add", "c").stdout)
        second = json.loads(self.run_todo("add", "d").stdout)
        self.assertEqual((first["id"], second["id"]), (5, 6))

    def test_12_invalid_store_exits_1_and_is_unchanged(self):
        for content in ("not json", '{"todos": 3}', "[]"):
            self.store.write_text(content)
            for args in (("add", "x"), ("list",)):
                self.assert_refused(self.run_todo(*args), code=1)
                self.assertEqual(self.store.read_text(), content)

    def test_13_unknown_command_and_extra_arguments(self):
        self.assert_refused(self.run_todo("frobnicate"))
        self.assert_refused(self.run_todo("list", "extra"))
        self.assertFalse(self.store.exists())

    def test_14_no_command_prints_usage(self):
        result = self.run_todo()
        self.assertEqual(result.returncode, 2)
        self.assertIn("usage", result.stderr)

    def test_15_unset_todo_file_exits_2(self):
        self.assert_refused(self.run_todo("add", "x", store=None))
        self.assert_refused(self.run_todo("list", store=None))


if __name__ == "__main__":
    unittest.main()
