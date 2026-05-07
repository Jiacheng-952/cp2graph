from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def semantic_hash(data: Any, digest_size: int = 16) -> str:
    payload = canonical_json(data).encode("utf-8")
    return hashlib.blake2b(payload, digest_size=digest_size).hexdigest()
