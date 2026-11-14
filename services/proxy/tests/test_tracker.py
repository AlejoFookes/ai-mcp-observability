import json

from multimcp_proxy.tracker import payload_bytes_of_result, tool_name_from_params


def test_tool_name_only_for_tools_call() -> None:
    assert tool_name_from_params("tools/call", {"name": "read_file"}) == "read_file"
    assert tool_name_from_params("tools/list", {"name": "read_file"}) is None
    assert tool_name_from_params("tools/call", {"name": 1}) is None
    assert tool_name_from_params("tools/call", None) is None


def test_payload_bytes_matches_spec_dumps() -> None:
    result = {"ok": True, "n": 1}
    assert payload_bytes_of_result(result) == len(json.dumps(result).encode("utf-8"))
