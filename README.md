# litigious-seller

An adversarial x402 seller used to exercise the buyer-side protections in
[BillGuard / pay-guard](https://github.com/sarmadahsan/pay-guard).

It is a plain [x402](https://pypi.org/project/x402/) v2 resource server
(FastAPI + the official payment middleware) on Base Sepolia. It exists so the
BillGuard demo has a counterparty that behaves badly, and so BillGuard's
reconciliation, duplicate-payment guard, fulfillment checks, and dispute flow
have something real to catch.

See the BillGuard design for the buyer side it pairs with:
https://github.com/sarmadahsan/pay-guard/blob/main/docs/billguard/design/design-final.md

## Layout

- `seller/` — the FastAPI app and routes
- `scripts/` — helpers (wallet setup, smoke clients)
- `tests/`

## Run

```bash
uv sync
cp .env.example .env   # set SELLER_PAY_TO and support contact
uv run uvicorn seller.app:app --port 8402
```

## Status

Scaffold only. The route behaviors are not implemented here.
