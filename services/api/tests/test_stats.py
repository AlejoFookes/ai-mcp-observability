from multimcp_api.repositories.stats import percentile_cont


def test_percentile_cont_matches_linear_interpolation() -> None:
    values = [10.0, 20.0, 30.0, 40.0, 100.0]
    assert percentile_cont(values, 0.50) == 30.0
    assert percentile_cont([1.0], 0.95) == 1.0
    assert percentile_cont([], 0.50) == 0.0
