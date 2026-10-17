from seller import stripe_recorder as sr


def test_atomic_usdc_to_cents():
    assert sr.atomic_usdc_to_cents(10000) == 1       # $0.01
    assert sr.atomic_usdc_to_cents("500000") == 50   # $0.50
    assert sr.atomic_usdc_to_cents("750000") == 75   # $0.75
    assert sr.atomic_usdc_to_cents(None) == 0


def test_encode_form_nested():
    params = {
        "amount": 50,
        "payment_method_data": {"type": "crypto"},
        "allowed_payment_method_types": ["crypto"],
        "payment_method_options": {
            "crypto": {
                "mode": "transaction_verification",
                "transaction_verification_options": {
                    "network": "base",
                    "transaction_hash": "0xabc",
                },
            }
        },
        "confirm": True,
    }
    pairs = dict(sr.encode_form(params))
    assert pairs["amount"] == "50"
    assert pairs["payment_method_data[type]"] == "crypto"
    assert pairs["allowed_payment_method_types[0]"] == "crypto"
    assert pairs["payment_method_options[crypto][mode]"] == "transaction_verification"
    assert pairs["payment_method_options[crypto][transaction_verification_options][network]"] == "base"
    assert pairs["payment_method_options[crypto][transaction_verification_options][transaction_hash]"] == "0xabc"
    assert pairs["confirm"] == "true"


def test_record_payment_disabled_is_noop(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    calls = []
    out = sr.record_payment("0xtx", 500000, post=lambda *a: calls.append(a) or {"id": "pi_x"})
    assert out is None
    assert calls == []  # poster never invoked when disabled


def test_record_payment_builds_correct_call(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("STRIPE_API_VERSION", "2026-07-29.preview")
    monkeypatch.setenv("STRIPE_PI_NETWORK", "base")
    captured = {}

    def fake_post(url, data, headers, auth):
        captured["url"] = url
        captured["data"] = dict(data)
        captured["headers"] = headers
        captured["auth"] = auth
        return {"id": "pi_123"}

    out = sr.record_payment("0xdeadbeef", "500000", success=True, post=fake_post)
    assert out == "pi_123"
    assert captured["url"].endswith("/payment_intents")
    assert captured["data"]["amount"] == "50"
    assert captured["data"]["payment_method_options[crypto][transaction_verification_options][transaction_hash]"] == "0xdeadbeef"
    assert captured["headers"]["Stripe-Version"] == "2026-07-29.preview"
    assert captured["headers"]["Idempotency-Key"] == "0xdeadbeef"
    assert captured["auth"] == ("sk_test_abc", "")


def test_record_payment_skips_failed_or_no_tx(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    assert sr.record_payment("0xtx", 500000, success=False, post=lambda *a: {"id": "x"}) is None
    assert sr.record_payment(None, 500000, success=True, post=lambda *a: {"id": "x"}) is None


def test_record_payment_skips_subcent(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    # 5000 atomic = 0.5 cent -> rounds to 0 -> skip
    assert sr.record_payment("0xtx", 5000, success=True, post=lambda *a: {"id": "x"}) is None


def test_record_payment_swallows_errors(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")

    def boom(*a):
        raise RuntimeError("stripe down")

    # Must not raise; returns None.
    assert sr.record_payment("0xtx", 500000, success=True, post=boom) is None
