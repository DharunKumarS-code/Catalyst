"""Pure schedule-generation tests: time zones, DST, start/end dates, horizon, adherence math."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.time import is_valid_timezone, zone
from app.services.medications import adherence_percent, period
from app.services.scheduling import plan_doses, to_utc

UTC = timezone.utc


def med(times, start, end=None, schedule_from=None, status="active", through=None):
    return {
        "times": times,
        "start_date": start,
        "end_date": end,
        "status": status,
        "schedule_from": schedule_from or datetime(2000, 1, 1, tzinfo=UTC),
        "scheduled_through": through,
    }


def test_new_york_winter_and_summer_offsets():
    ny = ZoneInfo("America/New_York")
    assert to_utc(datetime(2026, 1, 15).date(), "08:00", ny) == datetime(2026, 1, 15, 13, 0, tzinfo=UTC)
    assert to_utc(datetime(2026, 7, 15).date(), "08:00", ny) == datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


def test_kolkata_half_hour_offset():
    assert to_utc(datetime(2026, 3, 1).date(), "08:00", ZoneInfo("Asia/Kolkata")) == datetime(
        2026, 3, 1, 2, 30, tzinfo=UTC
    )


def test_auckland_local_date_differs_from_utc_date():
    # 08:00 on 10 June in Auckland (UTC+12) is 20:00 on 9 June in UTC.
    planned, _ = plan_doses(med(["08:00"], "2026-06-10", "2026-06-10"), ZoneInfo("Pacific/Auckland"),
                            datetime(2026, 6, 9, 0, 0, tzinfo=UTC), 7)
    assert [(p.local_date, p.scheduled_at) for p in planned] == [
        ("2026-06-10", datetime(2026, 6, 9, 20, 0, tzinfo=UTC))
    ]


def test_dst_transition_day_keeps_wall_clock_time():
    ny = ZoneInfo("America/New_York")
    planned, _ = plan_doses(med(["08:00"], "2026-03-07", "2026-03-09"), ny, datetime(2026, 3, 7, tzinfo=UTC), 7)
    # Clocks spring forward on 8 March 2026: 08:00 local moves from 13:00Z to 12:00Z.
    assert [p.scheduled_at.hour for p in planned] == [13, 12, 12]
    assert all(p.local_time == "08:00" for p in planned)


def test_skipped_dst_wall_time_still_produces_one_dose():
    ny = ZoneInfo("America/New_York")
    planned, _ = plan_doses(med(["02:30"], "2026-03-08", "2026-03-08"), ny, datetime(2026, 3, 8, tzinfo=UTC), 7)
    assert len(planned) == 1  # 02:30 does not exist that night; one dose, not zero or two


def test_multiple_times_per_day_and_bounded_horizon():
    now = datetime(2026, 5, 1, 0, 0, tzinfo=UTC)
    planned, through = plan_doses(med(["08:00", "14:00", "20:00"], "2026-05-01"), zone("UTC"), now, 7)
    assert len(planned) == 3 * 8  # today + 7 days ahead
    assert through == "2026-05-08"
    assert len({p.scheduled_at for p in planned}) == len(planned)


def test_respects_start_and_end_dates():
    now = datetime(2026, 5, 1, tzinfo=UTC)
    planned, _ = plan_doses(med(["09:00"], "2026-05-03", "2026-05-04"), zone("UTC"), now, 7)
    assert [p.local_date for p in planned] == ["2026-05-03", "2026-05-04"]


def test_ended_course_and_discontinued_generate_nothing():
    now = datetime(2026, 5, 10, tzinfo=UTC)
    assert plan_doses(med(["09:00"], "2026-04-01", "2026-04-30", schedule_from=now), zone("UTC"), now, 7) == ([], None)
    assert plan_doses(med(["09:00"], "2026-05-01", status="discontinued"), zone("UTC"), now, 7) == ([], None)


def test_schedule_from_and_watermark_prevent_regeneration():
    now = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
    planned, _ = plan_doses(med(["08:00", "20:00"], "2026-05-01", "2026-05-01", schedule_from=now),
                            zone("UTC"), now, 7)
    assert [p.local_time for p in planned] == ["20:00"]  # 08:00 is before schedule_from
    assert plan_doses(med(["08:00"], "2026-05-01", through="2026-05-08"), zone("UTC"), now, 7) == ([], None)
    later, _ = plan_doses(med(["08:00"], "2026-05-01", through="2026-05-08"), zone("UTC"),
                          now + timedelta(days=1), 7)
    assert [p.local_date for p in later] == ["2026-05-09"]  # only the newly reached day


def test_adherence_math_never_divides_by_zero():
    assert adherence_percent(0, 0) is None
    assert adherence_percent(3, 4) == 75.0
    assert adherence_percent(1, 3) == 33.3
    p = period("2026-05-01", "2026-05-07", [{"taken": 2, "missed": 1}, {"pending": 1}, {}])
    assert (p["total"], p["taken"], p["missed"], p["pending"], p["adherence_percent"]) == (4, 2, 1, 1, 50.0)


def test_timezone_validation():
    assert is_valid_timezone("Europe/London")
    assert not is_valid_timezone("Mars/Olympus")
    assert not is_valid_timezone("America")
    assert not is_valid_timezone("../etc/passwd")
    assert zone("nonsense").key == "UTC"
