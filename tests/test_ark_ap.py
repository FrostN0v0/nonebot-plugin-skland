from datetime import datetime

import pytest


@pytest.mark.parametrize(
    ("current", "recovery_delta", "expected"),
    [
        (180, 3600, 180),
        (180, -3600, 180),
        (135, 3600, 135),
        (60, 27_000, 60),
        (60, 26_639, 61),
        (60, 54_000, 60),
        (60, -3600, 135),
    ],
)
def test_ap_preserves_overflow_and_bounds_natural_recovery(app, mocker, current, recovery_delta, expected):
    from nonebot_plugin_skland.schemas.arknights.models.status import AP

    now = 1_700_000_000
    clock = mocker.patch("nonebot_plugin_skland.schemas.arknights.models.status.datetime")
    clock.now.return_value = datetime.fromtimestamp(now)
    ap = AP(current=current, max=135, lastApAddTime=now, completeRecoveryTime=now + recovery_delta)

    assert ap.ap_now == expected
