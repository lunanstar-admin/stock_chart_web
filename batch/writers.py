"""JSON 파일 원자적 쓰기 유틸."""

from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


def write_json(path: str | os.PathLike, payload: Any) -> None:
    """디렉토리 자동 생성 후 temp 파일 → rename (atomic)."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    clean = _sanitize(payload)
    fd, tmp_name = tempfile.mkstemp(
        prefix=p.name + ".", suffix=".tmp", dir=str(p.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(clean, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp_name, p)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
