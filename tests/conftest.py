from __future__ import annotations

import os

import pytest

from ponkan.hardware_gate import (
    manual_visual_tests_enabled,
    performance_tests_enabled,
    requires_n3dsxl_tests_enabled,
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    run_n3dsxl = requires_n3dsxl_tests_enabled(os.environ)
    run_performance = performance_tests_enabled(os.environ)
    run_manual_visual = manual_visual_tests_enabled(os.environ)

    skip_n3dsxl = pytest.mark.skip(reason="set PONKAN_RUN_N3DSXL=1 to run N3DSXL tests")
    skip_performance = pytest.mark.skip(
        reason="set PONKAN_RUN_PERFORMANCE=1 to run performance tests"
    )
    skip_manual_visual = pytest.mark.skip(
        reason="set PONKAN_RUN_MANUAL_VISUAL=1 to run manual visual tests"
    )

    for item in items:
        if "requires_n3dsxl" in item.keywords and not run_n3dsxl:
            item.add_marker(skip_n3dsxl)
        if "performance" in item.keywords and not run_performance:
            item.add_marker(skip_performance)
        if "manual_visual" in item.keywords and not run_manual_visual:
            item.add_marker(skip_manual_visual)
