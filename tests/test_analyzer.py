from pathlib import Path

from analyzer import analyze
from service import recent_errors, redact

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

CONFIG = {"function_name": "checkout", "memory_mb": 128, "timeout_seconds": 30, "table_name": "orders"}
SCHEMA = {
    "table_name": "orders",
    "billing_mode": "PROVISIONED",
    "keys": [{"name": "order_id", "type": "S", "role": "HASH"}],
    "global_secondary_indexes": [],
}
REPORT = (
    "REPORT RequestId: abc Duration: {duration} ms Billed Duration: 1 ms "
    "Memory Size: 128 MB Max Memory Used: {used} MB"
)


def _codes(findings: list[dict]) -> set[str]:
    return {finding["code"] for finding in findings}


def test_incident_fixture_yields_three_findings():
    config = json_loads(FIXTURES / "config.json")
    schema = json_loads(FIXTURES / "schema.json")
    logs = (FIXTURES / "logs.txt").read_text(encoding="utf-8")
    findings = analyze(config, schema, logs)
    assert _codes(findings) == {"memory_saturated", "duration_near_timeout", "dynamodb_throttled"}
    throttle = next(item for item in findings if item["code"] == "dynamodb_throttled")
    assert "沒有 GSI" in throttle["summary"]


def test_healthy_report_has_no_memory_or_duration_finding():
    logs = REPORT.format(duration=1000, used=40)
    assert analyze(CONFIG, SCHEMA, logs) == []


def test_memory_threshold_boundary():
    below = analyze(CONFIG, SCHEMA, REPORT.format(duration=1000, used=121))
    above = analyze(CONFIG, SCHEMA, REPORT.format(duration=1000, used=122))
    assert "memory_saturated" not in _codes(below)
    assert "memory_saturated" in _codes(above)


def test_duration_threshold_boundary():
    below = analyze(CONFIG, SCHEMA, REPORT.format(duration=25000, used=40))
    above = analyze(CONFIG, SCHEMA, REPORT.format(duration=29120.5, used=40))
    assert "duration_near_timeout" not in _codes(below)
    assert "duration_near_timeout" in _codes(above)


def test_throttle_with_gsi_does_not_claim_the_index_is_missing():
    schema = {
        **SCHEMA,
        "global_secondary_indexes": [
            {"name": "by_user", "keys": [{"name": "user_id", "type": "S", "role": "HASH"}]}
        ],
    }
    logs = "[ERROR] ProvisionedThroughputExceededException: exceeded"
    finding = analyze(CONFIG, schema, logs)[0]
    assert finding["code"] == "dynamodb_throttled"
    assert "沒有 GSI" not in finding["summary"]


def test_task_timeout_is_reported():
    findings = analyze(CONFIG, SCHEMA, "Task timed out after 30.00 seconds")
    assert _codes(findings) == {"timed_out"}


def test_redact_hides_api_token():
    cleaned = redact({"memory_mb": 128, "api_token": "super-secret-token", "nested": {"password": "x"}})
    assert cleaned["memory_mb"] == 128
    assert cleaned["api_token"] == "***"
    assert cleaned["nested"]["password"] == "***"


def test_recent_errors_uses_fixture_mode(monkeypatch):
    monkeypatch.setenv("AIOPS_MODE", "fixture")
    result = recent_errors()
    assert result["mode"] == "fixture"
    assert result["config"]["api_token"] == "***"
    assert "super-secret-token" not in str(result)
    assert _codes(result["findings"]) == {
        "memory_saturated",
        "duration_near_timeout",
        "dynamodb_throttled",
    }


def json_loads(path: Path) -> dict:
    import json

    return json.loads(path.read_text(encoding="utf-8"))
