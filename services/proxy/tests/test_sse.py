from multimcp_proxy.sse import iter_sse_data_payloads


def test_iter_sse_data_payloads_single_event() -> None:
    buf = [""]
    payloads = list(iter_sse_data_payloads("event: message\ndata: {\"a\":1}\n\n", buf))
    assert payloads == ['{"a":1}']
    assert buf[0] == ""


def test_iter_sse_data_payloads_across_chunks() -> None:
    buf = [""]
    assert list(iter_sse_data_payloads("data: {\"x\":", buf)) == []
    assert list(iter_sse_data_payloads("1}\n\n", buf)) == ['{"x":1}']


def test_iter_sse_multiline_data() -> None:
    buf = [""]
    block = "data: {\"a\":\ndata: 1}\n\n"
    assert list(iter_sse_data_payloads(block, buf)) == ['{"a":\n1}']
