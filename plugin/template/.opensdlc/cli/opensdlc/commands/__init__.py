# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0
from . import approvals, artifacts, metrics, operations, pipeline, quality
from .base import Command

COMMANDS: list[Command] = [
    *artifacts.COMMANDS,
    *pipeline.COMMANDS,
    *approvals.COMMANDS,
    *operations.COMMANDS,
    *quality.COMMANDS,
    *metrics.COMMANDS,
]
