# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
import shlex

OPERATORS = {"&&", "||", ";", "|", "&", "|&"}
REDIRECTS = {">", ">>", ">|", "&>", "&>>"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
IN_PLACE_EDITORS = {"sed", "perl", "gsed"}
DESTRUCTIVE = {"rm", "unlink", "truncate", "shred", "touch", "chmod", "chown", "ln"}


def tokens(command: str) -> list[str] | None:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;<>")
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def segments(command: str) -> list[tuple[str, list[str]]] | None:
    parts = tokens(command)
    if parts is None:
        return None
    found, current, joiner = [], [], ""
    for token in parts:
        if token in OPERATORS:
            found.append((joiner, current))
            current, joiner = [], token
        else:
            current.append(token)
    found.append((joiner, current))
    return [(j, words) for j, words in found if words]


def program(words: list[str]) -> tuple[str, list[str]]:
    rest = list(words)
    while rest and ASSIGNMENT.match(rest[0]):
        rest.pop(0)
    while rest and rest[0] in ("sudo", "env", "command", "exec", "nohup", "time"):
        rest.pop(0)
    return (rest[0].rsplit("/", 1)[-1], rest[1:]) if rest else ("", [])


def operands(args: list[str]) -> list[str]:
    return [a for a in args if not a.startswith("-") and a not in REDIRECTS]


def write_targets(command: str) -> list[str] | None:
    parsed = segments(command)
    if parsed is None:
        return None
    targets = []
    for _, words in parsed:
        for i, word in enumerate(words[:-1]):
            if word in REDIRECTS:
                targets.append(words[i + 1])
        name, args = program([w for i, w in enumerate(words) if w not in REDIRECTS and (i == 0 or words[i - 1] not in REDIRECTS)])
        files = operands(args)
        if name == "tee" or name in DESTRUCTIVE:
            targets += files
        elif name in ("cp", "install") and files:
            targets.append(files[-1])
        elif name == "mv":
            targets += files
        elif name in IN_PLACE_EDITORS and any(a == "-i" or a.startswith("-i") or a.startswith("--in-place") for a in args):
            targets += files[1:] if "-e" not in args else files
        elif name == "dd":
            targets += [a[3:] for a in args if a.startswith("of=")]
        elif name == "git" and args[:1] in (["checkout"], ["restore"]):
            targets += [a for a in files[1:] if a != "--"]
    return targets


def proven_segments(command: str) -> list[list[str]]:
    parsed = segments(command)
    if parsed is None or any(joiner not in ("", "&&") for joiner, _ in parsed):
        return []
    proven = []
    for _, words in parsed:
        name, args = program(words)
        proven.append([name, *args])
    return proven


def runs(command: str, expected: str) -> bool:
    wanted = tokens(expected) or []
    return any(words[: len(wanted)] == wanted for words in proven_segments(command))
