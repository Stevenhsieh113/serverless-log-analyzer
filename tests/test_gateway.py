import json
import time
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

from gateway import BotoGateway, FixtureGateway, normalize_table

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_fixture_gateway_reads_incident_files():
    gateway = FixtureGateway(FIXTURES)
    assert gateway.get_config("app-config", "checkout.json")["memory_mb"] == 128
    assert gateway.get_schema("orders")["global_secondary_indexes"] == []
    assert "Max Memory Used: 127" in gateway.get_logs("checkout", minutes=30)


def test_normalize_table_includes_gsi():
    table = {
        "TableName": "orders",
        "BillingModeSummary": {"BillingMode": "PAY_PER_REQUEST"},
        "AttributeDefinitions": [
            {"AttributeName": "order_id", "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        "KeySchema": [{"AttributeName": "order_id", "KeyType": "HASH"}],
        "GlobalSecondaryIndexes": [
            {
                "IndexName": "by_user",
                "KeySchema": [{"AttributeName": "user_id", "KeyType": "HASH"}],
            }
        ],
    }
    schema = normalize_table(table)
    assert schema["billing_mode"] == "PAY_PER_REQUEST"
    assert schema["global_secondary_indexes"][0]["name"] == "by_user"
    assert schema["global_secondary_indexes"][0]["keys"][0]["type"] == "S"


@mock_aws
def test_boto_gateway_reads_s3_config():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="app-config")
    s3.put_object(
        Bucket="app-config",
        Key="checkout.json",
        Body=json.dumps({"memory_mb": 128, "timeout_seconds": 30}).encode(),
    )
    config = BotoGateway().get_config("app-config", "checkout.json")
    assert config["memory_mb"] == 128
    assert config["timeout_seconds"] == 30


@mock_aws
def test_boto_gateway_missing_s3_object_raises_lookup_error():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="app-config")
    with pytest.raises(LookupError, match="checkout.json"):
        BotoGateway().get_config("app-config", "checkout.json")


@mock_aws
def test_boto_gateway_describes_dynamodb_table():
    dynamodb = boto3.client("dynamodb", region_name="us-east-1")
    dynamodb.create_table(
        TableName="orders",
        AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    schema = BotoGateway().get_schema("orders")
    assert schema["table_name"] == "orders"
    assert schema["billing_mode"] == "PROVISIONED"
    assert schema["keys"] == [{"name": "order_id", "type": "S", "role": "HASH"}]
    assert schema["global_secondary_indexes"] == []


@mock_aws
def test_boto_gateway_missing_table_raises_lookup_error():
    with pytest.raises(LookupError, match="missing"):
        BotoGateway().get_schema("missing")


@mock_aws
def test_boto_gateway_reads_recent_lambda_logs():
    logs = boto3.client("logs", region_name="us-east-1")
    logs.create_log_group(logGroupName="/aws/lambda/checkout")
    logs.create_log_stream(logGroupName="/aws/lambda/checkout", logStreamName="s1")
    logs.put_log_events(
        logGroupName="/aws/lambda/checkout",
        logStreamName="s1",
        logEvents=[
            {
                "timestamp": int(time.time() * 1000),
                "message": "REPORT RequestId: abc Duration: 10.0 ms Billed Duration: 10 ms Memory Size: 128 MB Max Memory Used: 40 MB",
            }
        ],
    )
    text = BotoGateway().get_logs("checkout", minutes=30)
    assert "Max Memory Used: 40" in text


@mock_aws
def test_boto_gateway_missing_log_group_raises_lookup_error():
    with pytest.raises(LookupError, match="/aws/lambda/missing"):
        BotoGateway().get_logs("missing", minutes=30)
