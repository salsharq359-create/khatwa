"""يتأكد إن الواجهة تنبني بدون أخطاء وإن الإجراءات تشتغل (بدون تشغيل Flet فعلي).

يتخطى نفسه إذا flet مو مثبت (مثلًا في خطوة اختبارات CI اللي تثبت pytest فقط).
"""
import asyncio
from datetime import datetime
from types import SimpleNamespace

import pytest

ft = pytest.importorskip("flet")
ftn = pytest.importorskip("flet_notifications")

import main as app_module  # noqa: E402
from store import FOCUSES, Store  # noqa: E402


class StubPage:
    def __init__(self):
        self.controls = []
        self.dialogs = []
        self.navigation_bar = None
        self.updates = 0

    def add(self, *controls):
        self.controls.extend(controls)

    def update(self):
        self.updates += 1

    def show_dialog(self, dialog):
        self.dialogs.append(dialog)


class FakeNotifications:
    def __init__(self, grant=True):
        self.grant = grant
        self.calls = []

    async def request_permissions(self):
        self.calls.append(("request_permissions",))
        return self.grant

    async def schedule(self, id, **kw):
        self.calls.append(("schedule", id, kw))

    async def cancel(self, id):
        self.calls.append(("cancel", id))


def make(tmp_path, grant=True, onboarded=True):
    store = Store(tmp_path / "s.json")
    if onboarded:
        store.finish_onboarding("ناصر", FOCUSES[0])
    page, notes = StubPage(), FakeNotifications(grant)
    app = app_module.App(page, store, notes)
    app.start()
    return app, page, store, notes


def switch_event(value):
    return SimpleNamespace(control=SimpleNamespace(value=value))


def test_welcome_then_home(tmp_path):
    app, page, store, _ = make(tmp_path, onboarded=False)
    assert page.navigation_bar is None and app.body.controls
    app.name_field.value = "  سارة "
    app.pick_focus(FOCUSES[1])
    app.start_app()
    assert store.onboarded and store.name == "سارة" and store.focus == FOCUSES[1]
    assert page.navigation_bar is app.nav


def test_every_screen_builds(tmp_path):
    app, page, store, _ = make(tmp_path)
    for i in range(4):
        app.goto_tab(i)
        assert app.body.controls, f"tab {i} is empty"
    app.open_settings()
    assert app.body.controls and page.navigation_bar is None
    app.back()
    assert page.navigation_bar is app.nav


def test_today_task_flow(tmp_path):
    app, _, store, _ = make(tmp_path)
    app.complete()
    assert store.today_done and len(store.achievements) == 1
    app.goto_tab(2)  # الإنجازات تعرض الخطوة
    assert app.body.controls
    app.goto_tab(0)  # الزر يتعطل بعد الإكمال ويختفي "خطوة أخف"


def test_lighter_gives_light_task(tmp_path):
    app, _, store, _ = make(tmp_path)
    app.lighter()
    assert store.data["light_today"] is True and store.achievements == []


def test_thought_save_and_empty(tmp_path):
    app, page, store, _ = make(tmp_path)
    app.goto_tab(1)
    app.save_thought()  # فاضي: تنبيه بس
    assert store.data["thoughts"] == [] and page.dialogs
    app.thought_field.value = "ما أقدر أخلص شي"
    app.step_field.value = "افتح الملف"
    app.save_thought()
    assert store.data["thoughts"][0]["thought"] == "ما أقدر أخلص شي"
    assert app.thought_field.value == "" and app.step_field.value == ""
    assert len(store.achievements) == 1
    app.goto_tab(1)  # يعرض "أفكار سابقة"


def test_mood_save_and_chart(tmp_path):
    app, _, store, _ = make(tmp_path)
    app.goto_tab(3)
    app.set_mood(5)
    app.set_energy(2)
    app.save_mood()
    assert store.data["moods"][0]["mood"] == 5 and store.recent_energy() == [2]
    app.goto_tab(3)


def test_heavy_day_toggle(tmp_path):
    app, _, store, _ = make(tmp_path)
    app.toggle_heavy(switch_event(True))
    assert store.heavy_day is True


def test_reminder_granted_schedules_daily_time_repeat(tmp_path):
    app, _, store, notes = make(tmp_path, grant=True)
    asyncio.run(app.toggle_reminder(switch_event(True)))
    assert store.reminder_on is True
    kind, rid, kw = notes.calls[-1][0], notes.calls[-1][1], notes.calls[-1][2]
    assert kind == "schedule" and rid == app_module.REMINDER_ID
    assert kw["when"] > datetime.now()
    assert (kw["when"].hour, kw["when"].minute) == (store.reminder_hour, store.reminder_minute)
    assert kw["match_components"] == ftn.DateTimeComponents.TIME


def test_reminder_denied_stays_off_with_message(tmp_path):
    app, page, store, notes = make(tmp_path, grant=False)
    asyncio.run(app.toggle_reminder(switch_event(True)))
    assert store.reminder_on is False
    assert page.dialogs and page.dialogs[-1].content.value == app_module.DENIED_MESSAGE
    assert not any(c[0] == "schedule" for c in notes.calls)


def test_reminder_off_cancels(tmp_path):
    app, _, store, notes = make(tmp_path)
    asyncio.run(app.toggle_reminder(switch_event(True)))
    asyncio.run(app.toggle_reminder(switch_event(False)))
    assert store.reminder_on is False and notes.calls[-1] == ("cancel", app_module.REMINDER_ID)


def test_pick_time_updates_and_reschedules(tmp_path):
    app, page, store, notes = make(tmp_path)
    asyncio.run(app.toggle_reminder(switch_event(True)))
    app.pick_time()
    picker = page.dialogs[-1]
    assert isinstance(picker, ft.TimePicker)
    picked = SimpleNamespace(control=SimpleNamespace(value=__import__("datetime").time(8, 30)))
    asyncio.run(picker.on_change(picked))
    assert (store.reminder_hour, store.reminder_minute) == (8, 30)
    assert notes.calls[-1][0] == "schedule" and notes.calls[-1][2]["when"].hour == 8


def test_reminder_errors_never_crash(tmp_path):
    app, _, store, notes = make(tmp_path)

    async def boom(*a, **k):
        raise RuntimeError("no platform")

    notes.schedule = boom
    store.set_reminder_on(True)
    asyncio.run(app.apply_reminder())  # يطبع الخطأ بس


@pytest.mark.parametrize(
    "h,m,expected",
    [(0, 0, "12:00 ص"), (9, 5, "9:05 ص"), (12, 0, "12:00 م"), (17, 30, "5:30 م"), (23, 59, "11:59 م")],
)
def test_format_time(h, m, expected):
    assert app_module.format_time(h, m) == expected
