# Prompt: write tests

Write pytest tests for <module>. Use tiny fixtures from `data/samples/` or synthetic arrays; no network. Cover: normal case, edge cases (night, zero wind, capacity limits, empty input), invariants (monotone quantiles, energy conservation, no leakage). Each test name states the behaviour. Mark anything slow with `@pytest.mark.slow`.
