# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

from .base import Adapter, AdapterError
from .cli import CliAdapter
from .http import HttpAdapter
from .library import LibraryAdapter
from .web import WebAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "cli": CliAdapter,
    "http": HttpAdapter,
    "library": LibraryAdapter,
    "web": WebAdapter,
}


def adapter_for(spec: dict, home: Path, workspace: Path) -> Adapter:
    return ADAPTERS[spec["type"]](workspace, spec, home)


__all__ = ["ADAPTERS", "Adapter", "AdapterError", "adapter_for"]
