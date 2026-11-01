# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re
from functools import lru_cache


@lru_cache(maxsize=256)
def compile_glob(pattern: str) -> re.Pattern:
    out = []
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out), re.S)


def matches(path: str, patterns: list[str]) -> bool:
    return any(compile_glob(p).fullmatch(path) for p in patterns)
