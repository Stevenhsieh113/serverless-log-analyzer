"""把 CloudWatch 日誌文字解析成結構化事件。此模組不碰網路。"""

from __future__ import annotations

import re

REPORT_PATTERN = re.compile(
    r"Duration:\s*(?P<duration>[\d.]+)\s*ms"
    r".*?Memory Size:\s*(?P<memory_size>\d+)\s*MB"
    r".*?Max Memory Used:\s*(?P<max_memory>\d+)\s*MB"
)


def parse_logs(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        event = parse_log_line(line)
        if event is not None:
            events.append(event)
    return events


def parse_log_line(line: str) -> dict | None:
    text = line.strip()
    if not text:
        return None
    if "Task timed out" in text:
        return {"kind": "timeout", "raw": text}
    if "ProvisionedThroughputExceeded" in text:
        return {"kind": "throttle", "raw": text}
    if text.startswith("REPORT"):
        matched = REPORT_PATTERN.search(text)
        if matched is None:
            return None
        return {
            "kind": "report",
            "duration_ms": float(matched.group("duration")),
            "memory_size_mb": int(matched.group("memory_size")),
            "max_memory_used_mb": int(matched.group("max_memory")),
            "raw": text,
        }
    if "ERROR" in text or "Exception" in text:
        return {"kind": "error", "raw": text}
    return None
