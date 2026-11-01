"""讀取 S3 設定、DynamoDB schema 與 Lambda 日誌。

FixtureGateway 讀專案裡的事故樣本。BotoGateway 呼叫 AWS API。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


class FixtureGateway:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def get_config(self, bucket: str, key: str) -> dict:
        return _read_json(self.root / "config.json")

    def get_schema(self, table_name: str) -> dict:
        return _read_json(self.root / "schema.json")

    def get_logs(self, function_name: str, minutes: int = 30) -> str:
        path = self.root / "logs.txt"
        if not path.is_file():
            raise LookupError(f"找不到日誌樣本：{path}")
        return path.read_text(encoding="utf-8")


class BotoGateway:
    def __init__(self, region: str = "us-east-1", s3=None, dynamodb=None, logs=None) -> None:
        self.region = region
        self._s3 = s3
        self._dynamodb = dynamodb
        self._logs = logs

    @property
    def s3(self):
        if self._s3 is None:
            self._s3 = boto3.client("s3", region_name=self.region)
        return self._s3

    @property
    def dynamodb(self):
        if self._dynamodb is None:
            self._dynamodb = boto3.client("dynamodb", region_name=self.region)
        return self._dynamodb

    @property
    def logs(self):
        if self._logs is None:
            self._logs = boto3.client("logs", region_name=self.region)
        return self._logs

    def get_config(self, bucket: str, key: str) -> dict:
        location = f"s3://{bucket}/{key}"
        try:
            obj = self.s3.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            _raise_lookup("讀取 S3 設定", location, exc)
        raw = obj["Body"].read().decode("utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"S3 設定不是 JSON：{location}") from exc
        if not isinstance(data, dict):
            raise ValueError(f"S3 設定必須是 JSON 物件：{location}")
        return data

    def get_schema(self, table_name: str) -> dict:
        try:
            response = self.dynamodb.describe_table(TableName=table_name)
        except ClientError as exc:
            _raise_lookup("讀取 DynamoDB schema", table_name, exc)
        return normalize_table(response["Table"])

    def get_logs(self, function_name: str, minutes: int = 30) -> str:
        group = f"/aws/lambda/{function_name}"
        start = int((datetime.now(timezone.utc) - timedelta(minutes=minutes)).timestamp() * 1000)
        try:
            response = self.logs.filter_log_events(
                logGroupName=group,
                startTime=start,
                limit=50,
            )
        except ClientError as exc:
            _raise_lookup("讀取 Lambda 日誌", group, exc)
        messages = [event["message"].rstrip("\n") for event in response.get("events", [])]
        return "\n".join(messages)


def normalize_table(table: dict) -> dict:
    attributes = {
        item["AttributeName"]: item["AttributeType"]
        for item in table.get("AttributeDefinitions", [])
    }

    def keys_of(key_schema: list[dict]) -> list[dict]:
        return [
            {
                "name": item["AttributeName"],
                "type": attributes.get(item["AttributeName"], ""),
                "role": item["KeyType"],
            }
            for item in key_schema
        ]

    indexes = []
    for index in table.get("GlobalSecondaryIndexes") or []:
        indexes.append({"name": index["IndexName"], "keys": keys_of(index.get("KeySchema", []))})
    billing = table.get("BillingModeSummary", {}).get("BillingMode", "PROVISIONED")
    return {
        "table_name": table["TableName"],
        "billing_mode": billing,
        "keys": keys_of(table.get("KeySchema", [])),
        "global_secondary_indexes": indexes,
    }


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise LookupError(f"找不到事故樣本：{path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"事故樣本必須是 JSON 物件：{path}")
    return data


def _raise_lookup(action: str, name: str, exc: ClientError) -> None:
    code = exc.response.get("Error", {}).get("Code", "ClientError")
    raise LookupError(f"無法{action}：{name}（{code}）") from exc
