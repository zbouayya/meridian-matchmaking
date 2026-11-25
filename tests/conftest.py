"""Suite-wide hooks: record what happened to each spec, then write the spec report."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Generator

import pytest

from tests.spec import report
from tests.spec.registry import REPO_ROOT


def pytest_configure(config: pytest.Config) -> None:
    outcomes: dict[str, list[report.Outcome]] = defaultdict(list)
    config.stash[report.OUTCOMES] = outcomes


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(
    item: pytest.Item, call: pytest.CallInfo[None]
) -> Generator[None, pytest.TestReport, pytest.TestReport]:
    result = yield
    spec_ids = [str(arg) for marker in item.iter_markers("spec") for arg in marker.args]
    # The call phase decides, unless setup already failed or skipped (a missing results file
    # is a skip raised by a fixture, during setup).
    decisive = result.when == "call" or (result.when == "setup" and result.outcome != "passed")
    if spec_ids and decisive:
        reason = ""
        if result.outcome == "skipped" and isinstance(result.longrepr, tuple):
            reason = str(result.longrepr[2]).removeprefix("Skipped: ")
        for spec_id in spec_ids:
            item.config.stash[report.OUTCOMES][spec_id].append(
                (item.nodeid, result.outcome, reason)
            )
    return result


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, exitstatus: int, config: pytest.Config
) -> None:
    counts = report.write(config)
    terminalreporter.write_sep("-", "specs")
    terminalreporter.write_line(report.summary_line(counts))
    terminalreporter.write_line(f"report: {report.REPORT_FILE.relative_to(REPO_ROOT)}")
