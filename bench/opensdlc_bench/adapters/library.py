# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import subprocess
from pathlib import Path

from .base import Adapter, AdapterError, Session

DRIVER = Path(__file__).with_name("library_driver.py")


class LibrarySession(Session):
    def __init__(self, adapter: "LibraryAdapter"):
        env = {**os.environ, "PYTHONPATH": str(adapter.workspace / adapter.spec["path"])}
        self.process = subprocess.Popen(["python3", "-P", str(DRIVER), json.dumps(adapter.spec)], cwd=adapter.workspace, env=env,
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def call(self, op: str, args: dict) -> object:
        try:
            self.process.stdin.write(json.dumps({"op": op, "args": args}) + "\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            pass
        line = self.process.stdout.readline()
        if not line:
            raise AdapterError(f"the library could not be loaded: {self.process.stderr.read()[-300:]}")
        reply = json.loads(line)
        if "crash" in reply:
            raise AdapterError(reply["crash"])
        return reply["value"]

    def close(self) -> None:
        self.process.kill()
        self.process.communicate()


class LibraryAdapter(Adapter):
    def session(self) -> Session:
        return LibrarySession(self)
