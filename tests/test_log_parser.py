from pathlib import Path

from log_parser import parse_log_line, parse_logs

FIXTURE_LOGS = Path(__file__).resolve().parents[1] / "fixtures" / "logs.txt"

REPORT = (
    "REPORT RequestId: abc\tDuration: 29120.50 ms\tBilled Duration: 29121 ms\t"
    "Memory Size: 128 MB\tMax Memory Used: 127 MB"
)


def test_parses_report_memory_and_duration():
    event = parse_log_line(REPORT)
    assert event["kind"] == "report"
    assert event["duration_ms"] == 29120.50
    assert event["memory_size_mb"] == 128
    assert event["max_memory_used_mb"] == 127


def test_parses_report_when_init_duration_is_between_fields():
    line = (
        "REPORT RequestId: abc Duration: 100.0 ms Billed Duration: 200 ms "
        "Init Duration: 80.0 ms Memory Size: 256 MB Max Memory Used: 40 MB"
    )
    event = parse_log_line(line)
    assert event["kind"] == "report"
    assert event["memory_size_mb"] == 256
    assert event["max_memory_used_mb"] == 40


def test_parses_throttle_timeout_and_generic_error():
    assert parse_log_line("Task timed out after 30.00 seconds")["kind"] == "timeout"
    throttle = parse_log_line("[ERROR] ProvisionedThroughputExceededException: exceeded")
    assert throttle["kind"] == "throttle"
    assert parse_log_line("[ERROR] RuntimeError: boom")["kind"] == "error"


def test_skips_blank_malformed_and_unrelated_lines():
    text = "\n\nSTART RequestId: abc\ngarbage %%%\nREPORT missing-fields\n" + REPORT
    kinds = [event["kind"] for event in parse_logs(text)]
    assert kinds == ["report"]


def test_empty_text_returns_no_events():
    assert parse_logs("") == []
    assert parse_log_line("   ") is None


def test_fixture_logs_contain_report_and_throttle():
    kinds = [event["kind"] for event in parse_logs(FIXTURE_LOGS.read_text(encoding="utf-8"))]
    assert kinds == ["throttle", "report"]
