# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import dataclasses
import importlib
import inspect
import json
import sys

spec = json.loads(sys.argv[1])
instance = getattr(importlib.import_module(spec["module"]), spec["factory"])()


class Unmapped(Exception):
    pass


def attributes(value: object) -> dict:
    found = dataclasses.asdict(value) if dataclasses.is_dataclass(value) else {}
    found |= getattr(value, "__dict__", {})
    found |= {name: getattr(value, name) for name, _ in inspect.getmembers(type(value), lambda m: isinstance(m, property))}
    return {k: plain(v) for k, v in found.items() if not k.startswith("_")}


def plain(value: object) -> object:
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if dataclasses.is_dataclass(value) or hasattr(value, "__dict__"):
        return attributes(value)
    return str(value)


def call(op: str, args: dict) -> object:
    if op not in spec["ops"]:
        raise Unmapped(f"this target maps no '{op}' operation")
    mapping = spec["ops"][op]
    names = [n.rstrip("?") for n in mapping.get("args", []) if not n.endswith("?") or n.rstrip("?") in args]
    result = plain(getattr(instance, mapping["call"])(*(args[n] for n in names)))
    return {mapping["as"]: result} if "as" in mapping else result


def kind(error: Exception) -> str | None:
    return next((spec["exceptions"][c.__name__] for c in type(error).__mro__ if c.__name__ in spec.get("exceptions", {})), None)


for line in sys.stdin:
    request = json.loads(line)
    try:
        reply = {"value": call(request["op"], request["args"])}
    except Unmapped as error:
        reply = {"crash": str(error)}
    except Exception as error:
        reply = {"value": {"error": kind(error)}} if kind(error) else {"crash": f"{type(error).__name__}: {error}"}
    print(json.dumps(reply, default=str), flush=True)
