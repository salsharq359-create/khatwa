from datetime import datetime, timedelta

import pytest

from store import FOCUSES, LIGHT_ACHIEVEMENT, Store
from tasks import LIGHT_TASKS, TASKS_BY_FOCUS


class Clock:
    def __init__(self, start=datetime(2026, 11, 12, 15, 0)):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(tmp_path, clock):
    return Store(tmp_path / "s.json", now=clock)


def test_defaults(store):
    assert store.onboarded is False
    assert store.focus == FOCUSES[0]
    assert store.reminder_on is False
    assert store.achievements == []


def test_complete_today_once(store):
    assert not store.today_done
    store.complete_today()
    assert store.today_done
    store.complete_today()  # الضغط مرتين ما يضيف إنجاز ثاني
    assert len(store.achievements) == 1
    assert store.achievements[0]["title"] == store.today_task.title


def test_lighter_gives_light_task_without_penalty(store):
    before = store.today_task
    store.lighter()
    assert store.today_task in LIGHT_TASKS
    assert store.today_task != before
    assert store.achievements == []  # ما فيه عقوبة ولا إنجاز وهمي


def test_heavy_day_uses_light_tasks(store):
    store.set_heavy_day(True)
    assert store.today_task in LIGHT_TASKS


def test_day_rollover_resets_light_and_skip(store, clock):
    store.lighter()
    clock.advance(days=1)
    assert store.today_task in TASKS_BY_FOCUS[store.focus]
    assert store.data["skip"] == 0
    assert store.data["light_today"] is False


def test_task_rotates_by_day(store, clock):
    seen = set()
    for _ in range(7):
        seen.add(store.today_task.title)
        clock.advance(days=1)
    assert len(seen) == 7


def test_week_marks_only_done_days(store, clock):
    store.complete_today()
    clock.advance(days=2)
    store.complete_today()
    week = store.week()
    assert len(week) == 7
    assert week[-1][0] == clock().date() and week[-1][1] is True
    assert week[-3][1] is True
    assert week[-2][1] is False  # اليوم اللي بينهم فاضي، وما نعاقب عليه
    assert store.week_count == 2


def test_thought_requires_text_and_step_counts_as_achievement(store):
    assert store.add_thought("  ", "a", "b", "c") is False
    assert store.add_thought("ما أقدر", "ما خلصت", "أقدر شوي", "افتح الملف") is True
    assert store.data["thoughts"][0]["thought"] == "ما أقدر"
    assert store.achievements[0]["title"] == LIGHT_ACHIEVEMENT


def test_thought_without_step_is_not_achievement(store):
    store.add_thought("فكرة", "", "", "")
    assert store.achievements == []


def test_mood_clamped_and_recent_energy_order(store, clock):
    store.add_mood(9, 0)
    assert store.data["moods"][0]["mood"] == 5
    assert store.data["moods"][0]["energy"] == 1
    for e in (2, 3, 4):
        clock.advance(hours=1)
        store.add_mood(3, e)
    assert store.recent_energy() == [1, 2, 3, 4]  # الأقدم أول


def test_persistence_roundtrip(tmp_path, clock):
    s1 = Store(tmp_path / "s.json", now=clock)
    s1.finish_onboarding("  ناصر ", "الشغل")
    s1.complete_today()
    s1.set_reminder_on(True)
    s1.set_reminder_time(8, 30)
    s2 = Store(tmp_path / "s.json", now=clock)
    assert s2.name == "ناصر"
    assert s2.focus == "الشغل"
    assert s2.onboarded is True
    assert s2.today_done is True
    assert (s2.reminder_on, s2.reminder_hour, s2.reminder_minute) == (True, 8, 30)


def test_corrupt_file_falls_back_to_defaults(tmp_path, clock):
    p = tmp_path / "s.json"
    p.write_text("{not json", encoding="utf-8")
    s = Store(p, now=clock)
    assert s.onboarded is False


def test_wrong_types_in_file_are_ignored(tmp_path, clock):
    p = tmp_path / "s.json"
    p.write_text('{"focus": "غير موجود", "reminder_hour": "x", "achievements": 5}', encoding="utf-8")
    s = Store(p, now=clock)
    assert s.focus == FOCUSES[0]
    assert s.reminder_hour == 17
    assert s.achievements == []


def test_reminder_time_wraps(store):
    store.set_reminder_time(25, 61)
    assert (store.reminder_hour, store.reminder_minute) == (1, 1)


def test_all_tasks_are_small_and_nonempty():
    pools = list(TASKS_BY_FOCUS.values()) + [LIGHT_TASKS]
    for pool in pools:
        assert pool
        for t in pool:
            assert t.title and t.hint
            assert 1 <= t.minutes <= 5
