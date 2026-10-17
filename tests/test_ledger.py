from seller.ledger import Ledger


def test_records_and_rolls_up_by_payer():
    led = Ledger()
    led.record(payer="0xAbC", route="GET /intel/AAPL", tx_hash="0xtx1",
               amount="$0.50", delivered=False, note="reported failure")
    led.record(payer="0xabc", route="GET /intel/AAPL", tx_hash="0xtx2",
               amount="$0.50", delivered=True, note="delivered on retry")
    led.record(payer="0xDEF", route="GET /dossier/AAPL", tx_hash="0xtx3",
               amount="$0.75", delivered=False, note="processing")

    assert len(led.all()) == 3
    summary = led.by_payer()
    # payer is normalized to lowercase, so the two 0xabc rows merge.
    assert summary["0xabc"]["charges"] == 2
    assert summary["0xabc"]["deliveries"] == 1
    assert summary["0xdef"]["charges"] == 1
    assert summary["0xdef"]["deliveries"] == 0
    assert "GET /intel/AAPL" in summary["0xabc"]["routes"]


def test_unknown_payer_defaults():
    led = Ledger()
    led.record(payer=None, route="GET /intel/AAPL")
    assert led.by_payer()["unknown"]["charges"] == 1


def test_reset_clears_rows():
    led = Ledger()
    led.record(payer="0x1", route="r")
    led.reset()
    assert led.all() == []
