# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import json
from pathlib import Path

CONFIG_PATH = Path(".opensdlc/config.json")
OUT_DIR = Path(".opensdlc/out")
CHANGES_DIR = Path("changes")


def load_config(root: Path) -> dict:
    path = root / CONFIG_PATH
    return json.loads(path.read_text()) if path.is_file() else {}


def out_path(root: Path, name: str) -> Path:
    path = root / OUT_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
