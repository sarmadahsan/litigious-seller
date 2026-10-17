from fastapi.testclient import TestClient

import seller.app as appmod
from seller.app import app
from seller.ledger import ledger

client = TestClient(app)


def test_health():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_published_contact_comes_from_env():
    r = client.get("/.well-known/x402-seller.json")
    assert r.status_code == 200
    body = r.json()
    assert body["support_email"] == "disputes@meridian-intel.example"
    assert body["support_phone"] == "+15555550123"
    assert body["network"] == "eip155:84532"
    assert body["pay_to"] == appmod.CONFIG.pay_to


def test_ledger_page_shows_recorded_rows():
    ledger.reset()
    ledger.record(payer="0xFEED", route="GET /intel/AAPL", tx_hash="0xdead",
                  amount="$0.50", delivered=False, note="reported failure")
    html = client.get("/ledger").text
    assert "0xfeed" in html
    assert "GET /intel/AAPL" in html
    assert "reported failure" in html


def test_ledger_json():
    ledger.reset()
    ledger.record(payer="0xBEEF", route="GET /dossier/AAPL", delivered=False)
    data = client.get("/ledger.json").json()
    assert data["by_payer"]["0xbeef"]["charges"] == 1
    assert data["rows"][0]["payer"] == "0xbeef"


def test_paid_routes_are_registered_with_middleware():
    assert "GET /intel/*" in appmod.ROUTES
    assert "GET /dossier/*" in appmod.ROUTES
    assert appmod.ROUTES["GET /intel/*"]["accepts"]["network"] == "eip155:84532"
