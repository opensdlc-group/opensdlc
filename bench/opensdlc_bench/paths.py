# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
REPO = BENCH.parent
PLUGIN = REPO / "plugin"
TEMPLATE = PLUGIN / "template"
TEMPLATE_CLI = TEMPLATE / ".opensdlc" / "cli"
SCENARIOS = BENCH / "scenarios"
RESULTS = BENCH / "results"

if str(TEMPLATE_CLI) not in sys.path:
    sys.path.insert(0, str(TEMPLATE_CLI))
