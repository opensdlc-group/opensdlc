# Copyright 2026 The OpenSDLC Authors
# SPDX-License-Identifier: Apache-2.0

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.S)
HEADING = re.compile(r"^## (.+?)\s*$", re.M)
VOLATILE = re.compile(r"^(?:status|review-by):.*\n", re.M)
HASH_LENGTH = 12


def content_hash(text: str) -> str:
    match = FRONTMATTER.match(text)
    normalized = VOLATILE.sub("", match.group(1) + "\n") + "---\n" + match.group(2) if match else text
    return hashlib.sha256(normalized.encode()).hexdigest()[:HASH_LENGTH]


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip() and item.strip() != "none"]


@dataclass(frozen=True)
class Document:
    path: Path
    text: str
    meta: dict[str, str]
    body: str

    @classmethod
    def read(cls, path: Path) -> "Document":
        return cls.parse(path, path.read_text())

    @classmethod
    def parse(cls, path: Path, text: str) -> "Document":
        match = FRONTMATTER.match(text)
        if not match:
            return cls(path=path, text=text, meta={}, body=text)
        meta = {}
        for line in match.group(1).splitlines():
            key, sep, value = line.partition(":")
            if sep:
                meta[key.strip()] = value.strip()
        return cls(path=path, text=text, meta=meta, body=match.group(2))

    @property
    def hash(self) -> str:
        return content_hash(self.text)

    @property
    def headings(self) -> set[str]:
        return set(HEADING.findall(self.body))

    def section(self, name: str) -> str:
        match = re.search(rf"^## {re.escape(name)}\s*$(.*?)(?=^## |\Z)", self.body, re.M | re.S)
        return match.group(1).strip() if match else ""

    def listed(self, key: str) -> list[str]:
        return split_list(self.meta.get(key, ""))

    def with_meta(self, **values: str) -> str:
        front, body = FRONTMATTER.match(self.text).groups()
        for key, value in values.items():
            if re.search(rf"^{re.escape(key)}:", front, re.M):
                front = re.sub(rf"^{re.escape(key)}:.*$", f"{key}: {value}", front, flags=re.M)
            else:
                front += f"\n{key}: {value}"
        return f"---\n{front}\n---\n{body}"
