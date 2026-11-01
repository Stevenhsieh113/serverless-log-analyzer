# HW2：雲端日誌分析助手

## 專案目的

無伺服器應用出問題時，設定在 S3、資料表結構在 DynamoDB、錯誤在 CloudWatch Logs，三邊要分開查。這個專案做一個能獨立執行的分析工具：讀取這三邊，印出可對照的發現。

預設使用專案內的事故樣本，不需要 AWS 帳號。樣本描述的情況是：

- Lambda 記憶體 128 MB，日誌裡已使用 127 MB
- timeout 30 秒，日誌裡的執行時間約 29120 ms
- DynamoDB 資料表 `orders` 只有主鍵、沒有 GSI，日誌出現 `ProvisionedThroughputExceeded`

在 `aiops` 資料夾執行：

```text
.venv\Scripts\python cli.py analyze
```

輸出會包含「記憶體打滿」「執行時間貼近 timeout」「DynamoDB 被節流，且沒有 GSI」。環境變數 `AIOPS_MODE=live` 時，同一支程式改走 boto3，讀取真實的 S3、DynamoDB 與 CloudWatch。

## 如何與 AI 協作

這份作業在 Cursor 裡和 AI 一起做。協作方式是先把範圍講清楚，再讓 AI 依這些決定寫程式。過程中由我定下的限制包括：

- 產品必須能單獨用命令列跑完，MCP 只是加分用的包裝
- 先用本地事故樣本，單元測試不連接真的 AWS
- 事故樣本放在 `fixtures/`，只保留對得出原因的那幾行
- Git 與 GitHub 留到程式和報告都完成後再處理
- 對話紀錄先不要匯出，之後需要再轉成可讀文件

AI 依上述決定產出解析器、Gateway、分析器、命令列、MCP Server 與測試。我以 `pytest` 的結果和 `cli.py analyze` 的輸出作為驗收，而不是只看程式是否生成。完整對話存在 Cursor 的 agent transcript，需要繳交時再整理成 Markdown。

## 如何把軟體工程實踐做進產品

程式分成四層，測試可以分開打：

| 模組 | 職責 |
| --- | --- |
| `log_parser.py` | 純函式。解析 REPORT、timeout、例外與 DynamoDB 節流 |
| `gateway.py` | 唯一會讀檔或呼叫 AWS 的邊界。`FixtureGateway` 讀樣本，`BotoGateway` 呼叫 S3、DynamoDB、CloudWatch Logs |
| `analyzer.py` | 把設定、schema 與日誌收成發現 |
| `service.py` | `cli.py` 與 `server.py` 共用的入口 |

`server.py` 的三個 MCP tool（`get_s3_config`、`get_dynamodb_schema`、`get_recent_lambda_errors`）只呼叫上面的入口，沒有另一套分析邏輯。設定裡的 token、密碼等欄位在回傳前會被遮成 `***`。

單元測試用 pytest。雲端 API 用 moto 的 `mock_aws` 模擬 S3 `GetObject`、DynamoDB `DescribeTable`、CloudWatch Logs `FilterLogEvents`，測試過程不需要 AWS credentials。執行方式：

```text
.venv\Scripts\python -m pytest
```

涵蓋的情況包括：日誌解析、記憶體與 timeout 的門檻、有無 GSI 時的節流說明、moto 模擬成功與資源不存在、命令列輸出，以及 MCP tool 回傳同一份發現。目前 26 項測試通過。

## MCP 加分項怎麼接上 Cursor

Cursor 是 MCP client。這個專案的 server 是 `server.py`。在 Cursor 的 MCP 設定加入：

```json
{
  "mcpServers": {
    "aiops": {
      "command": "C:\\Users\\USER\\OneDrive\\桌面\\科技輔助\\aiops\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Users\\USER\\OneDrive\\桌面\\科技輔助\\aiops\\server.py"],
      "env": {"AIOPS_MODE": "fixture"}
    }
  }
}
```

接上之後可以問：「幫我分析這個應用的最新日誌，並找出負載過高的原因。」模型會呼叫上述 tool，得到和命令列相同的三個發現。
