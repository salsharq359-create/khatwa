"""الحالة والتخزين المحلي لخطوة. بايثون صرف (بدون Flet) عشان ينختبر بسهولة.

كل البيانات في ملف JSON واحد على الجهاز، بدون حساب ولا سيرفر.

ملاحظة: هذا الملف أُعيدت كتابته من الـ bytecode الأصلي (store.cpython-313.pyc)
بعد ما انكتب فوقه بالغلط، والسلوك مطابق للأصل وتحققنا منه باختبارات المقارنة.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

from tasks import LIGHT_TASKS, TASKS_BY_FOCUS, StepTask  # noqa: F401

FOCUSES = ["الدراسة", "الشغل", "الحياة بشكل عام"]
LIGHT_ACHIEVEMENT = "كتبت فكرة وراجعتها بواقعية"

_DEFAULTS: dict = {
    "name": "",
    "focus": FOCUSES[0],
    "onboarded": False,
    "heavy_day": False,
    "reminder_on": False,
    "reminder_hour": 17,
    "reminder_minute": 0,
    "achievements": [],
    "thoughts": [],
    "moods": [],
    "day": "",
    "skip": 0,
    "light_today": False,
}


def default_path() -> Path:
    # على الموبايل Flet يعطينا مجلد دائم في FLET_APP_STORAGE_DATA
    base = os.getenv("FLET_APP_STORAGE_DATA")
    folder = Path(base) if base else Path.home() / ".khatwa"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "khatwa.json"


class Store:
    def __init__(self, path: Path | None = None, now: Callable[[], datetime] = datetime.now):
        self.path = Path(path) if path else default_path()
        self._now = now
        self.data = self._load()
        self._roll_day()

    def __getattr__(self, key):
        # name / focus / onboarded / heavy_day / reminder_* ... تنقرأ مباشرة من data
        try:
            return self.__dict__["data"][key]
        except KeyError:
            raise AttributeError(key) from None

    # ---------- التخزين ----------
    def _load(self) -> dict:
        data = {k: list(v) if isinstance(v, list) else v for k, v in _DEFAULTS.items()}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                for key in _DEFAULTS:
                    # نقبل القيمة بس إذا نوعها نفس نوع الافتراضي (ملف تالف ما يكسر التطبيق)
                    if key in loaded and type(loaded[key]) is type(_DEFAULTS[key]):
                        data[key] = loaded[key]
        except (OSError, ValueError):
            pass
        if data["focus"] not in TASKS_BY_FOCUS:
            data["focus"] = FOCUSES[0]
        return data

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def _roll_day(self) -> None:
        today = self._now().date().isoformat()
        if self.data["day"] != today:
            self.data.update(day=today, skip=0, light_today=False)
            self.save()

    # ---------- الإنجازات ----------
    @property
    def achievements(self) -> list:
        return self.data["achievements"]

    # ---------- خطوة اليوم ----------
    @property
    def today_task(self) -> StepTask:
        self._roll_day()
        if self.data["heavy_day"] or self.data["light_today"]:
            pool = LIGHT_TASKS
        else:
            pool = TASKS_BY_FOCUS[self.data["focus"]]
        now = self._now()
        day_of_year = (now.date() - date(now.year, 1, 1)).days
        return pool[(day_of_year + self.data["skip"]) % len(pool)]

    @property
    def today_done(self) -> bool:
        title = self.today_task.title
        today = self._now().date().isoformat()
        return any(a["title"] == title and a["at"][:10] == today for a in self.achievements)

    def complete_today(self) -> None:
        if self.today_done:
            return
        task = self.today_task
        self._add_achievement(task.title, task.minutes)
        self.save()

    def lighter(self) -> None:
        """"مو اليوم؟ خذ خطوة أخف": مهمة أسهل بدون لوم ولا إنجاز وهمي."""
        self.data["light_today"] = True
        self.data["skip"] += 1
        self.save()

    def _add_achievement(self, title: str, minutes: int) -> None:
        self.achievements.insert(
            0, {"title": title, "minutes": minutes, "at": self._now().isoformat(timespec="seconds")}
        )

    # ---------- الأسبوع ----------
    def week(self) -> list[tuple[date, bool]]:
        """آخر ٧ أيام (الأقدم أول، اليوم آخر واحد): هل فيه إنجاز؟"""
        today = self._now().date()
        done_days = {a["at"][:10] for a in self.achievements}
        days = [today - timedelta(days=6 - i) for i in range(7)]
        return [(d, d.isoformat() in done_days) for d in days]

    @property
    def week_count(self) -> int:
        return sum(1 for _, done in self.week() if done)

    # ---------- الأفكار ----------
    def add_thought(self, thought: str, evidence: str, alternative: str, step: str) -> bool:
        thought = thought.strip()
        if not thought:
            return False
        self.data["thoughts"].insert(
            0,
            {
                "thought": thought,
                "evidence": evidence.strip(),
                "alternative": alternative.strip(),
                "step": step.strip(),
                "at": self._now().isoformat(timespec="seconds"),
            },
        )
        # كتابة الفكرة ومراجعتها فعل بحد ذاته: تنحسب إنجاز إذا كتب الخطوة الصغيرة.
        if step.strip():
            self._add_achievement(LIGHT_ACHIEVEMENT, 3)
        self.save()
        return True

    # ---------- المزاج ----------
    def add_mood(self, mood: int, energy: int) -> None:
        mood = min(5, max(1, int(mood)))
        energy = min(5, max(1, int(energy)))
        self.data["moods"].insert(
            0, {"mood": mood, "energy": energy, "at": self._now().isoformat(timespec="seconds")}
        )
        self.save()

    def recent_energy(self) -> list[int]:
        """آخر ٧ قيم للطاقة (الأقدم أول)."""
        last = self.data["moods"][:7]
        return [m["energy"] for m in reversed(last)]

    # ---------- الإعدادات ----------
    def finish_onboarding(self, name: str, focus: str) -> None:
        self.data["name"] = name.strip()
        self.data["focus"] = focus if focus in TASKS_BY_FOCUS else FOCUSES[0]
        self.data["onboarded"] = True
        self.save()

    def set_heavy_day(self, value: bool) -> None:
        self.data["heavy_day"] = bool(value)
        self.save()

    def set_reminder_on(self, value: bool) -> None:
        self.data["reminder_on"] = bool(value)
        self.save()

    def set_reminder_time(self, hour: int, minute: int) -> None:
        self.data["reminder_hour"] = int(hour) % 24
        self.data["reminder_minute"] = int(minute) % 60
        self.save()
