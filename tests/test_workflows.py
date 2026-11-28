"""The two runs' workflow files are copies: the same steps and the same pinned versions, kept equal by hand."""

from tests.samples import ROOT

WORKFLOWS = ROOT / ".github" / "workflows"


def steps(name: str) -> list[str]:
    # Without the comment on top, which says what each run does.
    lines = (WORKFLOWS / name).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if not line.startswith("#")]


def test_the_reports_workflow_differs_from_the_calls_one_only_in_the_five_lines_that_name_its_run() -> None:
    calls, reports = steps("calls.yml"), steps("reports.yml")
    assert [pair for pair in zip(calls, reports, strict=True) if pair[0] != pair[1]] == [
        ("name: Daily run", "name: Weekly reports run"),
        ('- cron: "17 6 * * *"', '- cron: "17 20 * * 1"'),
        ("calls:", "reports:"),
        (
            "run: uv run --locked --no-dev python -m field_monitoring_pipeline.calls calls .archive/data",
            "run: uv run --locked --no-dev python -m field_monitoring_pipeline.calls reports .archive/data",
        ),
        (
            'git diff --staged --quiet || git commit -m "chore(data): store the run of $(date -u +%Y-%m-%d)"',
            'git diff --staged --quiet || git commit -m "chore(data): store the reports run of $(date -u +%Y-%m-%d)"',
        ),
    ]
