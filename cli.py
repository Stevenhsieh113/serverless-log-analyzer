"""產品入口。不透過 MCP 也能完成同一次分析。"""

from __future__ import annotations

import argparse
import sys

from service import recent_errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aiops",
        description="分析 Lambda 設定、DynamoDB schema 與近期日誌。",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze", help="讀取事故資料並印出發現")
    analyze.add_argument("--function", default="checkout", help="Lambda 函式名稱")
    analyze.add_argument("--minutes", type=int, default=30, help="向前回溯的分鐘數")
    analyze.add_argument("--bucket", default="app-config", help="設定檔所在的 S3 bucket")
    analyze.add_argument("--key", default="checkout.json", help="設定檔的 S3 key")
    analyze.add_argument("--table", default="orders", help="DynamoDB 資料表名稱")
    return parser


def format_report(result: dict) -> str:
    lines = [
        f"模式：{result['mode']}",
        f"資料來源：{result['source']}",
        f"應用 {result['function_name']} 的分析結果",
    ]
    findings = result["findings"]
    if not findings:
        lines.append("沒有發現異常訊號。")
        return "\n".join(lines)
    for index, finding in enumerate(findings, start=1):
        lines.append(f"{index}. {finding['summary']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    if args.command == "analyze":
        result = recent_errors(
            function_name=args.function,
            minutes=args.minutes,
            bucket=args.bucket,
            key=args.key,
            table_name=args.table,
        )
        print(format_report(result))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
