"""Create a Stripe crypto deposit address for Base, to use as the seller payTo.

Per https://docs.stripe.com/payments/machine/x402 : payments on Base are sent to
this static address, and Stripe records them. In a Stripe SANDBOX this is a test
address and moves no real money. Keep this off the request path; run it once and
put the result in SELLER_PAY_TO.

Run:
  STRIPE_SECRET_KEY=sk_test_... uv run python scripts/create_deposit_address.py
"""

from __future__ import annotations

import os
import sys

import httpx

API_VERSION = os.environ.get("STRIPE_API_VERSION", "2026-07-29.preview")


def main() -> int:
    key = os.environ.get("STRIPE_SECRET_KEY", "").strip()
    if not key:
        print("ERROR: set STRIPE_SECRET_KEY (use a sandbox sk_test_... key).")
        return 2
    if not key.startswith("sk_test_"):
        print("WARNING: this key is not a sandbox sk_test_ key. "
              "A live key creates a real on-chain deposit address.")
    resp = httpx.post(
        "https://api.stripe.com/v1/crypto/deposit_addresses",
        data={"network": "base"},
        headers={"Stripe-Version": API_VERSION},
        auth=(key, ""),
        timeout=30,
    )
    if resp.status_code >= 300:
        print(f"ERROR {resp.status_code}: {resp.text[:400]}")
        return 1
    body = resp.json()
    addr = body.get("address") or body.get("deposit_address") or body
    print("deposit address response:")
    print(body)
    print()
    print(f"Set this as your seller payTo:\n  SELLER_PAY_TO={addr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
