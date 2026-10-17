# How BillGuard catches this seller and opens a dispute

This document is the contract between `litigious-seller` and the buyer-side
protections in [pay-guard / BillGuard](https://github.com/sarmadahsan/pay-guard).
It describes the behavior each paid route is meant to exhibit, what evidence
BillGuard records, how it reaches the verdict, and how the dispute is opened
against the contact the seller publishes.

Buyer-side design reference:
https://github.com/sarmadahsan/pay-guard/blob/main/docs/billguard/design/design-final.md

## The two behaviors (implemented in `seller/app.py`)

### A. Double-charge — `GET /intel/{ticker}`
The seller settles the payment on-chain, then reports to the buyer that the
payment failed and no charge was made, so a naive buyer pays again. It keeps
doing this for the first attempts from a given payer and only returns the report
once it has been paid several times.

Why a stock agent falls for it: with the plain `x402` SDK the second 402 is
handed back to the caller. The *agent* decides to retry, and a naive agent
retries a "payment failed" automatically. Each retry is a fresh, valid on-chain
payment. `scripts/smoke.py --retries 2` reproduces this with an unprotected
client.

### B. Charge without delivery — `GET /dossier/{ticker}`
The seller settles the payment and returns HTTP 200 with a plausible
"your dossier is being compiled" receipt and an `order_id`. The status route it
points at (`GET /dossier/status/{order_id}`) always reports `processing`. The
goods never arrive. A naive agent records the order as placed and moves on.

## What BillGuard records (evidence)

For every purchase, before each network step:
- the signed payment payload (`from`, `nonce`, `validBefore`, encoded header)
- the offered price, asset, network, and `payTo` from the 402
- the raw seller response (status, headers incl. `PAYMENT-RESPONSE`, body)
- an on-chain `authorizationState(from, nonce)` check result with block number

## Detection

### A. Double-charge
1. Seller returns a 402 "payment failed." BillGuard does **not** trust it.
2. It polls `authorizationState(from, nonce)` on the USDC contract. The
   authorization is **used** → the money moved. Verdict: `SETTLED` plus
   `PAID_NO_DELIVERY` (settled, no artifact).
3. A retry for the same purchase intent hits the duplicate guard
   (`DUPLICATE_SUSPECTED`); the agent has no tool that can force a second
   payment. A reworded request to the same service is blocked by
   `SERVICE_QUARANTINED` once an unresolved `PAID_NO_DELIVERY` finding exists.
4. Contrast: the unprotected client in `scripts/smoke.py` shows two or more
   on-chain transfers for the same report. `/ledger` shows the same from the
   seller's own books.

Key invariant: a seller's claim that a payment failed is never trusted over the
chain. On-chain settlement state decides the money outcome.

### B. Charge without delivery
1. Seller returns 200 with a receipt. The payment settled.
2. BillGuard runs the route's validators on the body: `json_schema` (the real
   report shape), `non_empty`, `content_type`. The "processing" receipt fails
   the schema → `FULFILLMENT_FAILED`, with the receipt body stored as evidence.
   The finding stays open; polling the status route never flips it.

## Dispute

When a finding is unresolved (`PAID_NO_DELIVERY` or `FULFILLMENT_FAILED`),
BillGuard can open a dispute. It addresses it using the seller's **published**
contact, fetched from:

    GET /.well-known/x402-seller.json
    -> { "name", "support_email", "support_phone", "network", "pay_to" }

(The same email/phone also appear in each route's 402 `description`.)

The dispute payload BillGuard assembles:
- seller name and `payTo`
- purchase intent id and attempt history
- settlement tx / on-chain `authorizationState` proof with block number
- amount, asset, network
- the finding (`PAID_NO_DELIVERY` / `FULFILLMENT_FAILED`) and its evidence
- for a double-charge: each duplicate on-chain transfer

Channels (buyer-side, not in this repo): an email draft to `support_email`, or a
call script / voice message to `support_phone`. Sending is gated on human
approval; the agent assembles the case but does not negotiate or move money.

## Demo beats this repo supports

1. `scripts/smoke.py --url .../intel/AAPL --retries 2` — unprotected agent pays
   two or three times for one report.
2. `/ledger` — the seller's own books show the double charge and the
   never-delivered dossier.
3. Switch to BillGuard: the intel purchase is reconciled on-chain, marked
   `PAID_NO_DELIVERY`, retry refused; the dossier is `FULFILLMENT_FAILED`.
4. BillGuard reads `/.well-known/x402-seller.json` and drafts the dispute to the
   published email and phone.
