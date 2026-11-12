"""خطوة: واجهة Flet 1.x مع تذكير يومي (flet-notifications).

ملاحظة: هذا الملف أُعيدت كتابته بعد ما انكتب فوق الأصل بالغلط. المنطق (store.py) مطابق للأصل،
والواجهة نفس الشاشات والألوان والنصوص، لكن الكود نفسه كتابة جديدة مو نسخة حرفية.
"""
from datetime import datetime, time, timedelta

import flet as ft
import flet_notifications as ftn

from store import FOCUSES, Store

BG = "#F6F3EE"
INK = "#1F2A28"
MUTED = "#5B6663"
GREEN = "#2B7363"
DARK_GREEN = "#1F4F44"
MINT = "#E3F0EB"
LINE = "#E6E0D6"
DOT_OFF = "#ECE7DE"
WHITE = "#FFFFFF"
SOFT = "#DCEDE8"
SUB = "#3F514C"
FIELD_BORDER = "#CFC8BB"
BAR = "#5E9F8E"

REMINDER_ID = 1
REMINDER_TITLE = "خطوة اليوم"
REMINDER_BODY = "خطوة صغيرة بس، دقايق معدودة. تعال شوف شنو اليوم."
DENIED_MESSAGE = "الإشعارات مقفلة. فعّلها من إعدادات الجهاز لو تبي التذكير."

# الاثنين = 0 ... الأحد = 6
WEEKDAY_LETTER = dict(zip(range(7), ["ن", "ث", "ر", "خ", "ج", "س", "ح"]))
W500, W600, W700 = ft.FontWeight.W_500, ft.FontWeight.W_600, ft.FontWeight.W_700
TABS = ["اليوم", "أفكار", "إنجازات", "مزاج"]


def format_time(hour: int, minute: int) -> str:
    h12 = hour % 12 or 12
    return f"{h12}:{minute:02d} {'ص' if hour < 12 else 'م'}"


def label(value, size=16, weight=None, color=INK, **kw):
    return ft.Text(value, size=size, weight=weight, color=color, **kw)


def card(content, bgcolor=WHITE, border=True, padding=20, radius=20, **kw):
    return ft.Container(
        content=content,
        bgcolor=bgcolor,
        border=ft.Border.all(1, LINE) if border else None,
        border_radius=radius,
        padding=padding,
        **kw,
    )


def big_button(text, on_click, bg=GREEN, fg=WHITE, disabled=False):
    return ft.Row(
        [
            ft.FilledButton(
                content=text,
                on_click=on_click,
                disabled=disabled,
                expand=True,
                height=52,
                style=ft.ButtonStyle(
                    bgcolor={ft.ControlState.DISABLED: SOFT, ft.ControlState.DEFAULT: bg},
                    color={ft.ControlState.DISABLED: DARK_GREEN, ft.ControlState.DEFAULT: fg},
                    shape=ft.RoundedRectangleBorder(radius=16),
                    text_style=ft.TextStyle(size=17, weight=W700),
                ),
            )
        ]
    )


class App:
    """كل الحالة في Store، والواجهة بس ترسم وتنادي الإجراءات."""

    def __init__(self, page: ft.Page, store: Store, notifications):
        self.page = page
        self.store = store
        self.notifications = notifications
        self.tab = 0
        self.screen = "tabs"  # tabs | settings
        self.focus = FOCUSES[0]
        self.mood = 3
        self.energy = 3

        # الحقول كائنات ثابتة عشان النص المكتوب ما يضيع لما نعيد الرسم.
        self.name_field = ft.TextField(hint_text="اكتب اسمك", filled=True, bgcolor=WHITE, border_radius=14)
        self.thought_field = ft.TextField(
            hint_text="مثال: ما أقدر أخلص شي", filled=True, bgcolor=WHITE, border_radius=14,
            text_style=ft.TextStyle(size=17, weight=W600),
        )
        self.evidence_field = self._multiline("شنو الشي اللي يخليك تصدق الفكرة؟")
        self.alt_field = self._multiline("جملة أرحم وأقرب للحقيقة")
        self.step_field = self._multiline("شي تسويه في 5 دقايق")

        self.body = ft.Column(spacing=14, scroll=ft.ScrollMode.AUTO, expand=True)
        self.nav = ft.NavigationBar(
            selected_index=0,
            on_change=lambda e: self.goto_tab(int(e.control.selected_index)),
            bgcolor=WHITE,
            indicator_color=MINT,
            destinations=[
                ft.NavigationBarDestination(icon=ft.Icons.HOME_OUTLINED, selected_icon=ft.Icons.HOME, label=TABS[0]),
                ft.NavigationBarDestination(icon=ft.Icons.EDIT_OUTLINED, selected_icon=ft.Icons.EDIT, label=TABS[1]),
                ft.NavigationBarDestination(icon=ft.Icons.CHECK_CIRCLE_OUTLINE, selected_icon=ft.Icons.CHECK_CIRCLE, label=TABS[2]),
                ft.NavigationBarDestination(icon=ft.Icons.MOOD_OUTLINED, selected_icon=ft.Icons.MOOD, label=TABS[3]),
            ],
        )

    @staticmethod
    def _multiline(hint):
        return ft.TextField(
            hint_text=hint, multiline=True, min_lines=2, max_lines=3,
            filled=True, bgcolor=WHITE, border_radius=14,
        )

    # ---------- الإقلاع والرسم ----------
    def start(self):
        p = self.page
        p.title = "خطوة"
        p.rtl = True
        p.bgcolor = BG
        p.padding = 0
        p.theme = ft.Theme(color_scheme_seed=GREEN)
        p.theme_mode = ft.ThemeMode.LIGHT
        p.add(
            ft.SafeArea(
                expand=True,
                content=ft.Container(
                    content=self.body,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=24, vertical=20),
                ),
            )
        )
        self.render()

    def render(self):
        s = self.store
        if not s.onboarded:
            self.page.navigation_bar = None
            controls = self.welcome_view()
        elif self.screen == "settings":
            self.page.navigation_bar = None
            controls = self.settings_view()
        else:
            self.nav.selected_index = self.tab
            self.page.navigation_bar = self.nav
            controls = [self.home_view, self.thoughts_view, self.achievements_view, self.mood_view][self.tab]()
        self.body.controls = controls
        self.page.update()

    def toast(self, message: str):
        self.page.show_dialog(ft.SnackBar(content=ft.Text(message)))

    def goto_tab(self, i: int):
        self.tab = i
        self.screen = "tabs"
        self.render()

    # ---------- التذكير ----------
    async def apply_reminder(self):
        """يجدول التذكير اليومي (أو يلغيه). أي فشل يتجاهل بدون ما يوقف التطبيق."""
        try:
            if not self.store.reminder_on:
                await self.notifications.cancel(REMINDER_ID)
                return
            now = datetime.now()
            when = now.replace(hour=self.store.reminder_hour, minute=self.store.reminder_minute, second=0, microsecond=0)
            if when <= now:
                when += timedelta(days=1)
            await self.notifications.schedule(
                REMINDER_ID,
                when=when,
                title=REMINDER_TITLE,
                body=REMINDER_BODY,
                match_components=ftn.DateTimeComponents.TIME,
            )
        except Exception as ex:  # noqa: BLE001
            print(f"reminder error: {ex}")

    async def toggle_reminder(self, e):
        if e.control.value:
            try:
                granted = await self.notifications.request_permissions()
            except Exception as ex:  # noqa: BLE001
                print(f"permission error: {ex}")
                granted = False
            if not granted:
                self.store.set_reminder_on(False)
                self.render()
                self.toast(DENIED_MESSAGE)
                return
            self.store.set_reminder_on(True)
        else:
            self.store.set_reminder_on(False)
        await self.apply_reminder()
        self.render()

    def pick_time(self, e=None):
        async def changed(ev):
            t = ev.control.value
            if t is None:
                return
            self.store.set_reminder_time(t.hour, t.minute)
            await self.apply_reminder()
            self.render()

        self.page.show_dialog(
            ft.TimePicker(value=time(self.store.reminder_hour, self.store.reminder_minute), on_change=changed)
        )

    # ---------- الإجراءات ----------
    def start_app(self, e=None):
        self.store.finish_onboarding(self.name_field.value or "", self.focus)
        self.render()

    def pick_focus(self, focus: str):
        self.focus = focus
        self.render()

    def complete(self, e=None):
        self.store.complete_today()
        self.render()

    def lighter(self, e=None):
        self.store.lighter()
        self.render()

    def open_settings(self, e=None):
        self.screen = "settings"
        self.render()

    def back(self, e=None):
        self.screen = "tabs"
        self.render()

    def save_thought(self, e=None):
        ok = self.store.add_thought(
            self.thought_field.value or "",
            self.evidence_field.value or "",
            self.alt_field.value or "",
            self.step_field.value or "",
        )
        if not ok:
            self.toast("اكتب الفكرة أول.")
            return
        for f in (self.thought_field, self.evidence_field, self.alt_field, self.step_field):
            f.value = ""
        self.toast("انحفظت. خطوة حلوة.")
        self.render()

    def set_mood(self, v: int):
        self.mood = v
        self.render()

    def set_energy(self, v: int):
        self.energy = v
        self.render()

    def save_mood(self, e=None):
        self.store.add_mood(self.mood, self.energy)
        self.toast("انحفظ.")
        self.render()

    def toggle_heavy(self, e):
        self.store.set_heavy_day(bool(e.control.value))
        self.render()

    # ---------- الشاشات ----------
    def welcome_view(self):
        chips = ft.Row(
            wrap=True, spacing=10, run_spacing=10,
            controls=[
                ft.Chip(
                    label=ft.Text(f), selected=(f == self.focus), show_checkmark=False,
                    selected_color=MINT, on_click=lambda e, f=f: self.pick_focus(f),
                )
                for f in FOCUSES
            ],
        )
        return [
            ft.Container(height=24),
            ft.Container(
                width=64, height=64, border_radius=20, bgcolor=GREEN, alignment=ft.Alignment.CENTER,
                content=ft.Icon(ft.Icons.TRENDING_UP, color=WHITE, size=34),
            ),
            label("خطوة", 44, W700),
            label("خطوة صغيرة كل يوم، وتتغير الطريقة اللي تشوف فيها نفسك.", 18, color=MUTED),
            ft.Container(height=8),
            label("شنو اسمك؟", 15, W600),
            self.name_field,
            ft.Container(height=4),
            label("شنو أكثر شي يوقفك؟", 15, W600),
            chips,
            ft.Container(height=16),
            big_button("نبدأ", self.start_app),
            label("خطوة أداة دعم وعادات يومية، وما تغني عن مختص إذا كنت تحتاج واحد.", 13, color=MUTED,
                  text_align=ft.TextAlign.CENTER),
        ]

    def home_view(self):
        s = self.store
        task, done = s.today_task, s.today_done
        name = f"، {s.name}" if s.name else ""

        header = ft.Row(
            [
                ft.Column([label("مرحبا", 14, color=MUTED), label(f"أهلًا{name}", 24, W700)], spacing=2, expand=True),
                ft.IconButton(icon=ft.Icons.TUNE, tooltip="الإعدادات", on_click=self.open_settings),
            ]
        )

        task_items = [
            ft.Row([label("خطوة اليوم", 14, W600, SOFT), label(f"{task.minutes} دقايق", 14, color=SOFT)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            label(task.title, 26, W700, WHITE),
            label(task.hint, 15, color=SOFT),
            big_button("سويتها، عاش عليك" if done else "سويتها", self.complete, bg=WHITE, fg=DARK_GREEN, disabled=done),
        ]
        if not done:
            task_items.append(
                ft.Row(
                    [ft.TextButton(content="مو اليوم؟ خذ خطوة أخف", on_click=self.lighter,
                                   style=ft.ButtonStyle(color=SOFT))],
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            )

        dots = ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                ft.Column(
                    [
                        ft.Container(width=32, height=32, border_radius=16, bgcolor=GREEN if d_done else DOT_OFF),
                        label(WEEKDAY_LETTER[d.weekday()], 12, color=MUTED),
                    ],
                    spacing=6, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
                for d, d_done in s.week()
            ],
        )

        return [
            header,
            card(ft.Column(task_items, spacing=14), bgcolor=GREEN, border=False, padding=24, radius=24),
            card(
                ft.Column(
                    [
                        ft.Row([label("هذا الأسبوع", 16, W600), label(f"{s.week_count} أيام", 14, color=MUTED)],
                               alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        dots,
                        label("كل خطوة تحسب، حتى الصغيرة.", 14, color=MUTED),
                    ],
                    spacing=14,
                )
            ),
            card(
                ft.Row(
                    [
                        ft.Column([label("فيه فكرة ثقيلة؟", 16, W600), label("اكتبها وخلنا نشوفها بواقعية", 14, color=SUB)],
                                  spacing=4, expand=True),
                        ft.Icon(ft.Icons.CHEVRON_LEFT, color=DARK_GREEN),
                    ]
                ),
                bgcolor=MINT, border=False, padding=16, ink=True, on_click=lambda e: self.goto_tab(1),
            ),
        ]

    def _question(self, n, text, field):
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(width=26, height=26, border_radius=13, bgcolor=GREEN,
                                     alignment=ft.Alignment.CENTER, content=label(str(n), 14, W700, WHITE)),
                        label(text, 16, W600),
                    ],
                    spacing=10,
                ),
                field,
            ],
            spacing=6,
        )

    def thoughts_view(self):
        items = [
            label("مفكرة الأفكار", 26, W700),
            label("3 أسئلة بس، وتشوف الفكرة بشكل ثاني.", 14, color=MUTED),
            card(ft.Column([label("الفكرة اللي في بالك", 14, W600, MUTED), self.thought_field], spacing=6), padding=16),
            self._question(1, "شنو الدليل؟", self.evidence_field),
            self._question(2, "شنو البديل الواقعي؟", self.alt_field),
            self._question(3, "شنو أصغر خطوة؟", self.step_field),
            big_button("احفظ", self.save_thought),
        ]
        history = self.store.data["thoughts"][:5]
        if history:
            items.append(label("أفكار سابقة", 14, W600, MUTED))
            for t in history:
                lines = [label(t["thought"], 16, W600)]
                if t["alternative"]:
                    lines.append(label(f"بصورة أرحم: {t['alternative']}", 14, color=SUB))
                items.append(card(ft.Column(lines, spacing=6), bgcolor=MINT, border=False, padding=14, radius=16))
        return items

    def _day_label(self, iso: str) -> str:
        today = datetime.fromisoformat(iso[:10]).date()
        now = self.store._now().date()
        if today == now:
            return "اليوم"
        if today == now - timedelta(days=1):
            return "أمس"
        return f"{today.day}/{today.month}"

    def achievements_view(self):
        items = self.store.achievements
        out = [
            label("إنجازاتي", 26, W700),
            card(
                ft.Row(
                    [
                        ft.Column(
                            [label("سويت لين الحين", 14, color=SUB),
                             label(f"{len(items)} خطوة", 34, W700, DARK_GREEN),
                             label("كل وحدة منها دليل إنك تقدر.", 14, color=SUB)],
                            spacing=6, expand=True,
                        ),
                        ft.Container(width=64, height=64, border_radius=32, bgcolor=GREEN, alignment=ft.Alignment.CENTER,
                                     content=ft.Icon(ft.Icons.CHECK, color=WHITE, size=32)),
                    ]
                ),
                bgcolor=MINT, border=False, padding=22, radius=24,
            ),
        ]
        if not items:
            out.append(label("لسا ما فيه شي هنا. أول خطوة تسويها بتظهر هنا.", 14, color=MUTED,
                             text_align=ft.TextAlign.CENTER))
        for a in items:
            out.append(
                card(
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=GREEN),
                            label(a["title"], 16, W500, expand=True),
                            ft.Column([label(self._day_label(a["at"]), 13, color=MUTED),
                                       label(f"{a['minutes']} د", 12, color=MUTED)],
                                      spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
                        ],
                        spacing=12,
                    ),
                    padding=14, radius=18,
                )
            )
        return out

    def _scale(self, title, value, on_pick, low, high):
        buttons = ft.Row(
            spacing=8,
            controls=[
                (ft.FilledButton if value == i else ft.OutlinedButton)(
                    content=str(i), expand=True, height=48, on_click=lambda e, i=i: on_pick(i),
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=14), padding=0),
                )
                for i in range(1, 6)
            ],
        )
        return card(
            ft.Column(
                [label(title, 16, W600), buttons,
                 ft.Row([label(low, 13, color=MUTED), label(high, 13, color=MUTED)],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN)],
                spacing=12,
            ),
            padding=18,
        )

    def mood_view(self):
        items = [
            label("مزاجي وطاقتي", 26, W700),
            label("نص دقيقة باليوم، عشان تعرف شنو يرفع طاقتك.", 14, color=MUTED),
            self._scale("كيف مزاجك الحين؟", self.mood, self.set_mood, "ثقيل", "ممتاز"),
            self._scale("وطاقتك؟", self.energy, self.set_energy, "مرهق", "نشيط"),
        ]
        energy = self.store.recent_energy()
        if energy:
            last = len(energy) - 1
            bars = ft.Row(
                height=96, spacing=8, vertical_alignment=ft.CrossAxisAlignment.END,
                controls=[
                    ft.Container(expand=True, height=16 * e, border_radius=8, bgcolor=GREEN if i == last else BAR)
                    for i, e in enumerate(energy)
                ],
            )
            items.append(card(ft.Column([label("طاقتك آخر التسجيلات", 16, W600), bars], spacing=12), padding=18))
        items.append(big_button("احفظ", self.save_mood))
        return items

    def settings_view(self):
        s = self.store
        return [
            ft.Row([label("الإعدادات", 26, W700, expand=True), ft.TextButton(content="رجوع", on_click=self.back)]),
            card(
                ft.Column(
                    [
                        self._switch_row("تذكير يومي", "إشعار واحد بس باليوم", s.reminder_on, self.toggle_reminder),
                        ft.Divider(height=1, color=LINE),
                        ft.Row(
                            [
                                label("وقت التذكير", 16, W600, expand=True),
                                ft.OutlinedButton(
                                    content=format_time(s.reminder_hour, s.reminder_minute),
                                    disabled=not s.reminder_on, on_click=self.pick_time,
                                ),
                            ]
                        ),
                        ft.Divider(height=1, color=LINE),
                        self._switch_row("وضع اليوم الثقيل", "خطوات أخف وبدون ضغط", s.heavy_day, self.toggle_heavy),
                    ],
                    spacing=12,
                ),
                padding=16,
            ),
            card(
                ft.Column(
                    [
                        label("تنبيه", 15, W700, DARK_GREEN),
                        label("خطوة أداة دعم وعادات يومية، وما تغني عن مختص. إذا حسيت إن الوضع ثقيل عليك لفترة "
                              "طويلة، تواصل مع مختص أو مرشد في جامعتك.", 14, color=SUB),
                    ],
                    spacing=8,
                ),
                bgcolor=MINT, border=False, padding=18,
            ),
        ]

    @staticmethod
    def _switch_row(title, subtitle, value, on_change):
        return ft.Row(
            [
                ft.Column([label(title, 16, W600), label(subtitle, 13, color=MUTED)], spacing=2, expand=True),
                ft.Switch(value=value, active_color=GREEN, on_change=on_change),
            ]
        )


async def main(page: ft.Page):
    store = Store()
    notifications = ftn.Notifications()
    app = App(page, store, notifications)
    app.start()
    # نعيد الجدولة كل فتحة: يضمن إن التذكير باقي بعد التحديثات أو تغيير المنطقة الزمنية.
    await app.apply_reminder()


if __name__ == "__main__":
    ft.run(main)
