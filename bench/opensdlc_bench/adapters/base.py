# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
import socket
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

PLACEHOLDER = re.compile(r"\{(\w+)\}")


class AdapterError(Exception):
    pass


def provided(template: str, args: dict) -> bool:
    return all(name in args for name in PLACEHOLDER.findall(template))


def fill(template: str, args: dict, encode: Callable[[str], str] = str) -> str:
    def value(match: re.Match) -> str:
        if match.group(1) not in args:
            raise AdapterError(f"'{template}' needs {match.group(1)}")
        return encode(str(args[match.group(1)]))
    return PLACEHOLDER.sub(value, template)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Session(ABC):
    @abstractmethod
    def call(self, op: str, args: dict) -> object: ...

    def close(self) -> None:
        pass


class Adapter(ABC):
    def __init__(self, workspace: Path, spec: dict, home: Path):
        self.workspace = workspace
        self.spec = spec
        self.home = home

    def operation(self, op: str) -> object:
        if op not in self.spec.get("ops", {}):
            raise AdapterError(f"this target maps no '{op}' operation")
        return self.spec["ops"][op]

    def prepare(self) -> None:
        pass

    @abstractmethod
    def session(self) -> Session: ...

    def stop(self) -> None:
        pass
