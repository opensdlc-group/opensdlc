# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import re

RULE = re.compile(r"(?:^|,)\s*(\w+)(?:\([^)]*\))?")
GOVERNED = {"Edit": ("Edit", "Write")}


def toolset(allowed: str) -> str:
    names = [tool for name in RULE.findall(allowed) for tool in GOVERNED.get(name, (name,))]
    return ",".join(dict.fromkeys(names))
