"""
Unit tests for Layer 2 scam-intent classifier.
Run:  python -m intelligence.test_intent      (or: pytest intelligence/test_intent.py)
Pure-Python — no torch/GPU needed.
"""
from intelligence.intent_classifier import score_intent


def test_benign_is_low():
    for text in [
        "hi mom, running late for dinner, see you soon",
        "let's meet at the cafe around 5pm tomorrow",
        "the cricket match was amazing yesterday",
    ]:
        assert score_intent(text)["intent_risk"] < 0.2, text


def test_credential_theft_fires():
    r = score_intent("Sir your account is blocked, share the OTP immediately")
    assert r["intent_risk"] >= 0.5
    assert r["top_category"] in {"credential_theft", "urgency_threat"}


def test_hinglish_scam_fires():
    r = score_intent("aapke naam pe warrant hai, turant paise transfer karo warna giraftaar")
    assert r["intent_risk"] >= 0.6, r


def test_hindi_devanagari_fires():
    r = score_intent("आपका केवाईसी अपडेट करना है, ओटीपी बताओ")
    assert r["intent_risk"] > 0.0, r


def test_empty_is_zero():
    assert score_intent("")["intent_risk"] == 0.0
    assert score_intent("   ")["intent_risk"] == 0.0


def test_multiple_categories_compound():
    single = score_intent("share the OTP")["intent_risk"]
    multi = score_intent(
        "this is the police, share the OTP and transfer the money immediately or arrest"
    )["intent_risk"]
    assert multi > single, (single, multi)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
