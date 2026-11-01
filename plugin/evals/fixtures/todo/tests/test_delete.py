import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Delete(unittest.TestCase):
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

    def assert_refused_unchanged(self, *args, code=2):
        before = self.store.read_bytes() if self.store.exists() else None
        self.assert_refused(self.run_todo(*args), code)
        after = self.store.read_bytes() if self.store.exists() else None
        self.assertEqual(before, after)

    def add_three(self):
        for title in ("Buy milk", "Walk dog", "Call mum"):
            self.run_todo("add", title)

    def listed(self):
        result = self.run_todo("list")
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)

    def added_id(self, title="Feed cat"):
        result = self.run_todo("add", title)
        self.assertEqual(result.returncode, 0)
        return json.loads(result.stdout)["id"]

    def test_1_delete_prints_the_deleted_id(self):
        self.add_three()
        result = self.run_todo("delete", "2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"deleted": 2})
        self.assertEqual(len(result.stdout.strip().splitlines()), 1)

    def test_2_deleted_todo_leaves_the_others_in_order(self):
        self.add_three()
        self.run_todo("delete", "2")
        self.assertEqual(
            self.listed(),
            [
                {"id": 1, "title": "Buy milk", "done": False},
                {"id": 3, "title": "Call mum", "done": False},
            ],
        )

    def test_3_delete_again_is_unknown_and_changes_nothing(self):
        self.add_three()
        self.run_todo("delete", "2")
        self.assert_refused_unchanged("delete", "2", code=3)

    def test_4_deleted_id_is_not_reissued(self):
        self.add_three()
        self.run_todo("delete", "2")
        self.assertEqual(self.added_id(), 4)

    def test_5_highest_deleted_id_is_not_reissued(self):
        self.add_three()
        self.run_todo("delete", "3")
        self.assertEqual(self.added_id(), 4)
        self.assertEqual(
            [(t["id"], t["title"]) for t in self.listed()[:2]],
            [(1, "Buy milk"), (2, "Walk dog")],
        )

    def test_6_deleting_everything_still_does_not_reissue_ids(self):
        self.add_three()
        for todo_id in ("1", "2", "3"):
            self.run_todo("delete", todo_id)
        self.assertEqual(self.run_todo("list").stdout.strip(), "[]")
        self.assertEqual(self.added_id(), 4)

    def test_7_done_todo_can_be_deleted(self):
        self.add_three()
        self.run_todo("done", "1")
        result = self.run_todo("delete", "1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"deleted": 1})
        self.assertEqual([t["id"] for t in self.listed()], [2, 3])

    def test_8_ids_are_matched_by_value_not_position(self):
        self.add_three()
        self.run_todo("delete", "1")
        self.assertEqual(
            [(t["id"], t["title"]) for t in self.listed()],
            [(2, "Walk dog"), (3, "Call mum")],
        )
        done = self.run_todo("done", "3")
        self.assertEqual(
            json.loads(done.stdout), {"id": 3, "title": "Call mum", "done": True}
        )
        self.assert_refused_unchanged("done", "1", code=3)

    def test_9_unknown_id_is_refused_and_changes_nothing(self):
        self.add_three()
        self.assert_refused_unchanged("delete", "7", code=3)

    def test_10_id_zero_is_unknown(self):
        self.add_three()
        self.assert_refused_unchanged("delete", "0", code=3)

    def test_11_unknown_id_does_not_create_the_store(self):
        self.assert_refused_unchanged("delete", "1", code=3)
        self.assertFalse(self.store.exists())

    def test_12_leading_zeros_read_as_decimal(self):
        self.add_three()
        result = self.run_todo("delete", "02")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"deleted": 2})
        self.assertEqual([t["id"] for t in self.listed()], [1, 3])

    def test_13_bad_arguments_are_invalid_input(self):
        self.add_three()
        for args in ((), ("1", "2"), ("abc",), ("-1",), ("1.0",), ("",), (" 1",)):
            with self.subTest(args=args):
                self.assert_refused_unchanged("delete", *args)

    def test_13_wrong_argument_count_names_delete(self):
        result = self.run_todo("delete")
        self.assertIn("delete", result.stderr)
        self.assertNotIn("done", result.stderr)

    def test_14_todo_file_unset_is_invalid_input(self):
        self.assert_refused(self.run_todo("delete", "1", store=None))

    def test_15_unreadable_store_exits_1_and_is_untouched(self):
        self.store.write_text("not json", encoding="utf-8")
        self.assert_refused_unchanged("delete", "1", code=1)


if __name__ == "__main__":
    unittest.main()
