# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import quote

from .base import Adapter, AdapterError, Session, fill, free_port


class HttpSession(Session):
    def __init__(self, adapter: "HttpAdapter"):
        self.adapter = adapter
        self.port = free_port()
        env = {**os.environ, adapter.spec["portEnv"]: str(self.port)}
        self.process = subprocess.Popen(adapter.spec["start"], cwd=adapter.workspace, env=env, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            self.wait_until_healthy(adapter.spec["health"])
        except AdapterError:
            self.close()
            raise

    def request(self, method: str, path: str, body: dict | None) -> tuple[int, object]:
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"} if body is not None else {}
        request = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        try:
            return status, json.loads(raw) if raw.strip() else None
        except ValueError:
            return status, raw.decode(errors="replace")[:200]

    def wait_until_healthy(self, path: str) -> None:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise AdapterError(f"the server exited: {self.process.stderr.read()[-300:]}")
            try:
                if self.request("GET", path, None)[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.2)
        raise AdapterError("the server did not become healthy within 60s")

    def call(self, op: str, args: dict) -> object:
        route = self.adapter.operation(op)
        path = fill(route["path"], args, lambda value: quote(value, safe=""))
        body = {k: args[k] for k in route["body"] if k in args} if "body" in route else None
        try:
            status, value = self.request(route["method"], path, body)
        except OSError as error:
            raise AdapterError(f"{op}: {error}") from error
        errors = self.adapter.spec.get("statuses", {})
        if str(status) in errors:
            return {"error": errors[str(status)]}
        if not 200 <= status < 300:
            raise AdapterError(f"{op} answered {status}: {str(value)[:200]}")
        return value

    def close(self) -> None:
        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        self.process.communicate(timeout=10)


class HttpAdapter(Adapter):
    def session(self) -> Session:
        return HttpSession(self)
