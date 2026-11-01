"""命令列與 MCP tool 共用的分析入口。"""

from __future__ import annotations

import os
from pathlib import Path

from analyzer import analyze
from gateway import BotoGateway, FixtureGateway

SECRET_KEY_PARTS = ("password", "secret", "token", "access_key", "private_key")


def fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"


def current_mode() -> str:
    mode = os.environ.get("AIOPS_MODE", "fixture").strip().lower()
    if mode not in {"fixture", "live"}:
        raise ValueError(f"不支援的 AIOPS_MODE：{mode}")
    return mode


def load_gateway():
    if current_mode() == "live":
        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        return BotoGateway(region=region)
    return FixtureGateway(fixture_dir())


def redact(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, item in value.items():
            if any(part in key.lower() for part in SECRET_KEY_PARTS):
                cleaned[key] = "***"
            else:
                cleaned[key] = redact(item)
        return cleaned
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def recent_errors(
    function_name: str = "checkout",
    minutes: int = 30,
    bucket: str = "app-config",
    key: str = "checkout.json",
    table_name: str = "orders",
) -> dict:
    gateway = load_gateway()
    config = redact(gateway.get_config(bucket, key))
    schema = gateway.get_schema(table_name)
    logs_text = gateway.get_logs(function_name, minutes)
    mode = current_mode()
    return {
        "mode": mode,
        "function_name": function_name,
        "config": config,
        "schema": schema,
        "findings": analyze(config, schema, logs_text),
        "source": _source_label(mode),
    }


def _source_label(mode: str) -> str:
    if mode == "fixture":
        return "fixtures/config.json、fixtures/schema.json、fixtures/logs.txt"
    return "AWS S3、DynamoDB、CloudWatch Logs"
