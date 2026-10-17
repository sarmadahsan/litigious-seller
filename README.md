# litigious-seller

An adversarial x402 seller ("Meridian Intel") used to exercise the buyer-side
protections in [BillGuard / pay-guard](https://github.com/sarmadahsan/pay-guard).

It is a plain [x402](https://pypi.org/project/x402/) v2 resource server
(FastAPI + the official payment middleware) on Base Sepolia. It exists so the
BillGuard demo has a counterparty that misbehaves, and so BillGuard's
reconciliation, duplicate-payment guard, fulfillment checks, and dispute flow
have something real to catch.

Buyer-side design it pairs with:
https://github.com/sarmadahsan/pay-guard/blob/main/docs/billguard/design/design-final.md

## Two behaviors

- **Double-charge** (`GET /intel/{ticker}`): settles, then tells the buyer the
  payment failed so a naive buyer pays again.
- **Charge without delivery** (`GET /dossier/{ticker}`): settles, returns a
  "processing" receipt, never delivers.

How BillGuard is expected to detect each and open a dispute is written up in
[docs/billguard-detection-and-dispute.md](docs/billguard-detection-and-dispute.md).

## Layout

- `seller/app.py` — FastAPI app, x402 middleware wiring, honest endpoints
- `seller/ledger.py` — the seller's own settlement books (`/ledger`)
- `seller/config.py` — env-backed config
- `scripts/setup_wallet.py` — config check and faucet links
- `scripts/smoke.py` — unprotected x402 buyer baseline (`--retries` to replay a retry)
- `tests/` — ledger and endpoint tests
- `docs/` — the detection + dispute spec

## Endpoints

| Route | Paid | Status |
|---|---|---|
| `GET /intel/{ticker}` | $0.50 | **you implement** (double-charge) |
| `GET /dossier/{ticker}` | $0.75 | **you implement** (no delivery) |
| `GET /dossier/status/{id}` | free | **you implement** (always processing) |
| `GET /ledger`, `/ledger.json` | free | implemented |
| `GET /.well-known/x402-seller.json` | free | implemented (dispute contact) |
| `GET /` | free | implemented (health) |

The payment middleware already gates `GET /intel/*` and `GET /dossier/*`. Add the
handlers in `seller/app.py` where marked; call `ledger.record(...)` to write a
row.

## Run

```bash
uv sync
cp .env.example .env          # set SELLER_PAY_TO and support contact
uv run python scripts/setup_wallet.py
uv run uvicorn seller.app:app --port 8402
uv run pytest
```

## Optional: record payments to Stripe

The seller can mirror every settled payment into Stripe as a PaymentIntent, so
the Stripe Dashboard becomes a second, independent view of what was charged (a
double charge shows up as two PaymentIntents). This uses Stripe's x402 machine
payments, which is the same protocol/network/currency this seller already uses,
so it is an add-on, not a rail change. See
https://docs.stripe.com/payments/machine/x402

It is **off unless `STRIPE_SECRET_KEY` is set**, and the recording never affects
the payment flow (it runs in an after-settle hook that never raises). Use a
Stripe **sandbox** key for the demo: no real money, and no crypto payment-method
approval (that and the US-only limit apply to live mode only).

```bash
# 1. Mint a Base deposit address in your Stripe sandbox
STRIPE_SECRET_KEY=sk_test_... uv run python scripts/create_deposit_address.py
# 2. Put the printed address in SELLER_PAY_TO, and set STRIPE_SECRET_KEY in .env
# 3. Run the server as usual; settled payments now appear in the Stripe Dashboard
```

Pieces: `seller/stripe_recorder.py` (PaymentIntent recording, direct REST, fully
unit-tested), `scripts/create_deposit_address.py` (one-time deposit address), and
an after-settle hook in `seller/app.py` registered only when a key is present.

## Verifying the double charge on-chain

The point of the demo is that a seller's HTTP response cannot be trusted about
money. `scripts/verify_double_charge.py` ignores the seller entirely and reads
Base Sepolia directly: it counts the USDC transfers that actually moved from the
buyer wallet to the seller's `payTo` in a block window.

```bash
uv run python scripts/verify_double_charge.py \
    --buyer  0xYOURBUYER \
    --pay-to 0xSELLERPAYTO \
    --from-block <block before the test>
```

- **0 or 1 transfer** -> no double charge in that window.
- **2+ transfers** for one logical purchase -> double charge proven from the
  chain, no matter what the seller's responses said.

This is the same on-chain settlement check BillGuard performs instead of
believing a 402 "payment failed" response. Why the gap exists: x402 settles the
payment before it finishes the HTTP response, so the on-chain fact and the HTTP
status are independent. A "failed" status is not proof the money stayed put.

## What's implemented vs not

The payment wiring, ledger, published contact, scripts, tests, and the
detection/dispute spec are done and tested against x402 2.25.0. The two paid
route behaviors are left as marked stubs in `seller/app.py`.
