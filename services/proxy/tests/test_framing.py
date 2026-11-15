from multimcp_proxy.framing import decode_line, encode_line


def test_decode_valid_json_line() -> None:
    frame = decode_line(b'{"jsonrpc":"2.0","id":1,"method":"ping"}')
    assert frame.ok is True
    assert frame.text.startswith("{")


def test_decode_invalid_json_line() -> None:
    frame = decode_line(b"not-json")
    assert frame.ok is False


def test_decode_empty_line() -> None:
    frame = decode_line(b"")
    assert frame.ok is False


def test_encode_preserves_payload() -> None:
    text = '{"jsonrpc":"2.0","id":"a","method":"x","params":{"n":1},"_meta":{"v":"2026-07-28"}}'
    assert encode_line(text) == (text + "\n").encode("utf-8")
