# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import argparse
from pathlib import Path

from .commands import COMMANDS
from .config import load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="opensdlc")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    subcommands = parser.add_subparsers(dest="command", required=True)
    registry = {}
    for command in COMMANDS:
        command.configure(subcommands.add_parser(command.name, help=command.help))
        registry[command.name] = command
    args = parser.parse_args(argv)
    root = args.root.resolve()
    return registry[args.command].run(args, root, load_config(root))
