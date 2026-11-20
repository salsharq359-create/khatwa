from thoughts_ai import normalize, suggest


def test_normalize_handles_tashkeel_and_hamza():
    assert normalize("أَنَا عَاجِزَةٌ") == "انا عاجزه"


def test_inability_thought_gets_alternatives_and_steps():
    s = suggest("أنا عاجزة أن أعمل في برنامج التسويق بالعمولة")
    assert not s.crisis
    assert s.patterns[0][0] == "فكرة العجز"
    assert len(s.alternatives) >= 3 and s.steps
    assert any("المنتج" in step for step in s.steps)   # خطوة مخصصة لموضوع الشغل/التسويق


def test_exam_motivation_gets_study_step():
    s = suggest("ما لي خلق أدرس للامتحان")
    assert s.patterns[0][0] == "انتظار الرغبة قبل البدء"
    assert any("نموذج" in x or "الملف" in x or "ملف" in x for x in s.steps)


def test_generalization_and_failure_combine():
    s = suggest("أنا فاشلة دايم")
    assert {t for t, _ in s.patterns} == {"الحكم على النفس من تجربة وحدة", "التعميم: دايمًا وأبدًا"}


def test_unknown_text_falls_back_to_generic():
    s = suggest("شي غريب")
    assert s.patterns[0][0] == "فكرة تستحق نظرة ثانية" and s.alternatives


def test_crisis_text_returns_safety_message_not_alternatives():
    s = suggest("ابي اموت")
    assert s.crisis and "112" in s.message
    assert not s.alternatives and not s.steps
