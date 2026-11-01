import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Done(unittest.TestCase):
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

    def test_1_done_prints_the_todo_marked_done(self):
        self.add_three()
        result = self.run_todo("done", "2")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(
            json.loads(result.stdout), {"id": 2, "title": "Walk dog", "done": True}
        )

    def test_2_done_todo_stays_in_list_in_place(self):
        self.add_three()
        self.run_todo("done", "2")
        self.assertEqual(
            self.listed(),
            [
                {"id": 1, "title": "Buy milk", "done": False},
                {"id": 2, "title": "Walk dog", "done": True},
                {"id": 3, "title": "Call mum", "done": False},
            ],
        )

    def test_3_done_again_prints_the_same_and_changes_nothing(self):
        self.add_three()
        first = self.run_todo("done", "2")
        before = self.store.read_bytes()
        second = self.run_todo("done", "2")
        self.assertEqual(second.returncode, 0)
        self.assertEqual(json.loads(second.stdout), json.loads(first.stdout))
        self.assertEqual(self.store.read_bytes(), before)

    def test_4_done_output_equals_the_listed_item(self):
        self.add_three()
        done = json.loads(self.run_todo("done", "2").stdout)
        self.assertEqual(self.listed()[1], done)

    def test_8_leading_zeros_read_as_decimal(self):
        self.add_three()
        result = self.run_todo("done", "02")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["id"], 2)
        self.assertTrue(self.listed()[1]["done"])

    def test_12_next_id_is_untouched(self):
        self.add_three()
        self.run_todo("done", "2")
        added = json.loads(self.run_todo("add", "Feed cat").stdout)
        self.assertEqual(added["id"], 4)
        self.assertEqual(
            [t["title"] for t in self.listed()[:3]],
            ["Buy milk", "Walk dog", "Call mum"],
        )

    def test_5_6_unknown_id_exits_3_and_changes_nothing(self):
        self.add_three()
        for bad in ("7", "0"):
            self.assert_refused_unchanged("done", bad, code=3)
        self.assertIn("7", self.run_todo("done", "7").stderr)

    def test_7_unknown_id_without_a_store_leaves_it_absent(self):
        self.assert_refused_unchanged("done", "1", code=3)
        self.assertFalse(self.store.exists())

    def test_9_bad_arguments_exit_2_and_change_nothing(self):
        self.add_three()
        bad_args = [
            [],
            ["1", "2"],
            ["abc"],
            ["-1"],
            ["+1"],
            ["1.0"],
            [""],
            [" 1"],
            ["٣"],
        ]
        for args in bad_args:
            with self.subTest(args=args):
                self.assert_refused_unchanged("done", *args)

    def test_10_todo_file_unset_exits_2(self):
        self.assert_refused(self.run_todo("done", "1", store=None))

    def test_11_unreadable_store_exits_1_and_is_untouched(self):
        self.store.write_text("not json")
        self.assert_refused_unchanged("done", "1", code=1)
        self.assertEqual(self.store.read_text(), "not json")


if __name__ == "__main__":
    unittest.main()
