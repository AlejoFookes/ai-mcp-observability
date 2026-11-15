import pytest

from multimcp_proxy.cli import build_parser, main


def test_parser_stdio_requires_server_name() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["stdio", "--", "python", "-c", "pass"])


def test_parser_stdio_captures_command_after_dashdash() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["stdio", "--server-name", "filesystem", "--", "python", "-m", "mcp_server"]
    )
    assert args.command == "stdio"
    assert args.server_name == "filesystem"
    assert args.server_command == ["--", "python", "-m", "mcp_server"]


def test_main_errors_without_server_command() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["stdio", "--server-name", "x"])
    assert exc.value.code == 2
