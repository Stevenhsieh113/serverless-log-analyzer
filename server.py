"""MCP Server。三個 tool 只轉呼叫既有的分析功能。"""

from __future__ import annotations

import json

from mcp.server.mcpserver import MCPServer

from service import load_gateway, recent_errors, redact

mcp = MCPServer("aiops")


def get_s3_config(bucket: str = "app-config", key: str = "checkout.json") -> str:
    """讀取 S3 上的應用設定，並遮罩 token、密碼等欄位。fixture 模式回傳專案內建的事故樣本。"""
    config = redact(load_gateway().get_config(bucket, key))
    return json.dumps(config, ensure_ascii=False, indent=2)


def get_dynamodb_schema(table_name: str = "orders") -> str:
    """讀取 DynamoDB 資料表的主鍵、GSI 與計費模式。fixture 模式回傳專案內建的事故樣本。"""
    schema = load_gateway().get_schema(table_name)
    return json.dumps(schema, ensure_ascii=False, indent=2)


def get_recent_lambda_errors(
    function_name: str = "checkout",
    minutes: int = 30,
    bucket: str = "app-config",
    key: str = "checkout.json",
    table_name: str = "orders",
) -> str:
    """抓取近期 Lambda 日誌，結合 S3 設定與 DynamoDB schema，回傳記憶體、timeout 與節流發現。"""
    result = recent_errors(function_name, minutes, bucket, key, table_name)
    return json.dumps(result, ensure_ascii=False, indent=2)


mcp.tool()(get_s3_config)
mcp.tool()(get_dynamodb_schema)
mcp.tool()(get_recent_lambda_errors)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
