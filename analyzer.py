"""依設定、schema 與已解析日誌整理發現。"""

from __future__ import annotations

from log_parser import parse_logs

MEMORY_RATIO = 0.95
TIMEOUT_RATIO = 0.85


def analyze(config: dict, schema: dict, logs_text: str) -> list[dict]:
    events = parse_logs(logs_text)
    findings = []
    findings.extend(_memory_and_duration(config, events))
    throttle = _throttle(config, schema, events)
    if throttle is not None:
        findings.append(throttle)
    timeout = _timeout(events)
    if timeout is not None:
        findings.append(timeout)
    return findings


def _memory_and_duration(config: dict, events: list[dict]) -> list[dict]:
    reports = [event for event in events if event["kind"] == "report"]
    if not reports:
        return []
    report = max(reports, key=lambda event: event["duration_ms"])
    findings = []
    limit_mb = report["memory_size_mb"]
    used_mb = report["max_memory_used_mb"]
    if limit_mb and used_mb / limit_mb >= MEMORY_RATIO:
        findings.append(
            {
                "code": "memory_saturated",
                "summary": f"記憶體打滿：上限 {limit_mb} MB，日誌 Max Memory Used {used_mb} MB。",
                "evidence": report["raw"],
            }
        )
    timeout_seconds = float(config.get("timeout_seconds") or 0)
    if timeout_seconds and report["duration_ms"] >= timeout_seconds * 1000 * TIMEOUT_RATIO:
        duration = _format_ms(report["duration_ms"])
        timeout_label = _format_seconds(timeout_seconds)
        findings.append(
            {
                "code": "duration_near_timeout",
                "summary": f"執行時間貼近 timeout：上限 {timeout_label} 秒，日誌 Duration {duration} ms。",
                "evidence": report["raw"],
            }
        )
    return findings


def _throttle(config: dict, schema: dict, events: list[dict]) -> dict | None:
    throttles = [event for event in events if event["kind"] == "throttle"]
    if not throttles:
        return None
    table = schema.get("table_name") or config.get("table_name") or "unknown"
    indexes = schema.get("global_secondary_indexes") or []
    if indexes:
        summary = f"DynamoDB 被節流：資料表 {table} 出現 ProvisionedThroughputExceeded。"
    else:
        summary = (
            f"DynamoDB 被節流：資料表 {table} 沒有 GSI，"
            "日誌出現 ProvisionedThroughputExceeded。"
        )
    return {"code": "dynamodb_throttled", "summary": summary, "evidence": throttles[0]["raw"]}


def _timeout(events: list[dict]) -> dict | None:
    timeouts = [event for event in events if event["kind"] == "timeout"]
    if not timeouts:
        return None
    return {"code": "timed_out", "summary": "Lambda 任務逾時。", "evidence": timeouts[0]["raw"]}


def _format_ms(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def _format_seconds(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return f"{value:g}"
