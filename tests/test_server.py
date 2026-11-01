import json

import server


def test_s3_tool_redacts_token(monkeypatch):
    monkeypatch.setenv("AIOPS_MODE", "fixture")
    config = json.loads(server.get_s3_config())
    assert config["memory_mb"] == 128
    assert config["api_token"] == "***"


def test_schema_tool_returns_table_without_gsi(monkeypatch):
    monkeypatch.setenv("AIOPS_MODE", "fixture")
    schema = json.loads(server.get_dynamodb_schema())
    assert schema["table_name"] == "orders"
    assert schema["global_secondary_indexes"] == []


def test_log_tool_returns_the_same_three_findings(monkeypatch):
    monkeypatch.setenv("AIOPS_MODE", "fixture")
    result = json.loads(server.get_recent_lambda_errors())
    codes = {finding["code"] for finding in result["findings"]}
    assert codes == {"memory_saturated", "duration_near_timeout", "dynamodb_throttled"}
