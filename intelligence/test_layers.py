"""
Unit tests for Layer 3 (call signals) and 3-layer fusion.
Run:  python -m intelligence.test_layers    (pure-Python, no GPU)
"""
from intelligence.call_signals import score_call_signals
from intelligence.fusion import fuse_layers, verdict_from_risk


# ── Layer 3 ──
def test_helpline_is_trusted():
    assert score_call_signals({"number": "1930"})["call_signal_risk"] == 0.0


def test_blocklist_is_high():
    assert score_call_signals({"number": "+911234567890"})["call_signal_risk"] >= 0.85


def test_known_contact_is_low():
    r = score_call_signals({"number": "+919876543210", "in_contacts": True})
    assert r["call_signal_risk"] < 0.2


def test_bank_from_personal_mobile_flags():
    r = score_call_signals({"number": "+919812345678", "claimed_entity": "SBI Bank"})
    assert r["call_signal_risk"] >= 0.5


# ── Fusion ──
def test_deepfake_alone_flags():
    assert verdict_from_risk(fuse_layers(0.95, 0.0, 0.0)) == "FRAUD"


def test_human_scam_alone_flags():
    # genuine (non-fake) voice, but the CONVERSATION is a scam → still FRAUD
    assert verdict_from_risk(fuse_layers(0.10, 0.86, 0.20)) == "FRAUD"


def test_benign_stays_real():
    assert verdict_from_risk(fuse_layers(0.10, 0.00, 0.10)) == "REAL"


def test_fused_in_range():
    for v in (0, 0.5, 1):
        for i in (0, 0.5, 1):
            for s in (0, 0.5, 1):
                assert 0.0 <= fuse_layers(v, i, s) <= 1.0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        try:
            t(); print(f"  PASS  {t.__name__}"); passed += 1
        except AssertionError as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
