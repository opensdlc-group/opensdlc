# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import importlib.util
import os
import signal
import subprocess
import time
import urllib.request
from collections.abc import Callable
from types import ModuleType

from .base import Adapter, AdapterError, Session, free_port

SETTLE = 0.5
PATIENCE = 5.0


def until(condition: Callable[[], object], what: str, patience: float = PATIENCE) -> object:
    deadline = time.monotonic() + patience
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.05)
    raise AdapterError(f"timed out waiting for {what}")


class WebSession(Session):
    def __init__(self, adapter: "WebAdapter"):
        self.driver = adapter.driver
        self.context = adapter.browser.new_context()
        self.page = self.context.new_page()
        self.page.set_default_timeout(PATIENCE * 1000)
        self.page.goto(adapter.url)
        self.page.wait_for_load_state("networkidle")

    def call(self, op: str, args: dict) -> object:
        if op not in self.driver.OPS:
            raise AdapterError(f"this target maps no '{op}' operation")
        try:
            return self.driver.OPS[op](self.page, args)
        except AdapterError:
            raise
        except Exception as error:
            raise AdapterError(f"{op}: {str(error).splitlines()[0][:200]}") from error

    def close(self) -> None:
        self.context.close()


class WebAdapter(Adapter):
    def __init__(self, workspace, spec, home):
        super().__init__(workspace, spec, home)
        self.server = None
        self.playwright = None
        self.browser = None
        self.url = ""
        self.driver = self.load_driver()

    def load_driver(self) -> ModuleType:
        spec = importlib.util.spec_from_file_location(f"opensdlc_bench_driver_{self.home.name}", self.home / self.spec["driver"])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def prepare(self) -> None:
        build = subprocess.run(self.spec["build"], cwd=self.workspace, capture_output=True, text=True, timeout=300)
        if build.returncode != 0:
            raise AdapterError(f"build failed: {(build.stderr or build.stdout)[-300:]}")
        port = free_port()
        command = [part.replace("{port}", str(port)) for part in self.spec["serve"]]
        self.server = subprocess.Popen(command, cwd=self.workspace, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        self.url = f"http://127.0.0.1:{port}/"
        until(self.serving, "the preview server", patience=60)
        from playwright.sync_api import sync_playwright
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch()

    def serving(self) -> bool:
        try:
            with urllib.request.urlopen(self.url, timeout=2) as response:
                return response.status == 200
        except OSError:
            return False

    def session(self) -> Session:
        return WebSession(self)

    def stop(self) -> None:
        if self.browser:
            self.browser.close()
            self.playwright.stop()
        if self.server:
            try:
                os.killpg(self.server.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            self.server.wait(timeout=10)
