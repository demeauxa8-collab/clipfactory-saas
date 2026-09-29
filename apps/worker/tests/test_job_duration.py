import pytest

from app.pipeline.job_state import JobStateError, billable_minutes


@pytest.mark.parametrize("duration,expected", [(0.1, 1), (60, 1), (60.01, 2), (1800, 30)])
def test_billing_uses_unrounded_duration(duration, expected):
    assert billable_minutes(duration, 30) == expected


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf"), 1800.01])
def test_invalid_or_over_plan_duration_is_rejected(duration):
    with pytest.raises(JobStateError):
        billable_minutes(duration, 30)
