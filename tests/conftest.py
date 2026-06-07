from __future__ import annotations

import os

import pytest

from py3dscapture.hardware_gate import performance_tests_enabled, requires_n3dsxl_tests_enabled


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    run_n3dsxl = requires_n3dsxl_tests_enabled(os.environ)
    run_performance = performance_tests_enabled(os.environ)

    skip_n3dsxl = pytest.mark.skip(reason="set PONKAN_RUN_N3DSXL=1 to run N3DSXL tests")
    skip_performance = pytest.mark.skip(
        reason="set PONKAN_RUN_PERFORMANCE=1 to run performance tests"
    )

    for item in items:
        if "requires_n3dsxl" in item.keywords and not run_n3dsxl:
            item.add_marker(skip_n3dsxl)
        if "performance" in item.keywords and not run_performance:
            item.add_marker(skip_performance)
