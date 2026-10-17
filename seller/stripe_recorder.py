"""Record settled x402 payments to Stripe as PaymentIntents.

Honest bookkeeping bridge. After the x402 facilitator settles a payment on
Base, this records the on-chain transaction to Stripe in
``transaction_verification`` mode, so the payment shows up in the Stripe
Dashboard with normal reporting. It mirrors the flow in
https://docs.stripe.com/payments/machine/x402 (the docs show Node; this is the
same REST calls from Python).

Design choices:
  * Direct REST over httpx, so we are not pinned to a preview build of the
    Stripe Python SDK. The preview API version is sent as a header.
  * Never raises into the caller. This runs inside an x402 after-settle hook,
    and a raising after-settle hook is turned into a 402 by the SDK, which
    would corrupt the payment flow. On any error it logs and returns None.
  * No-op when STRIPE_SECRET_KEY is unset, so the seller runs exactly as before
    without Stripe configured.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Callable

import httpx

log = logging.getLogger("litigious-seller.stripe")

STRIPE_API = "https://api.stripe.com/v1"
# Sandbox preview version from the Stripe x402 docs. Override with STRIPE_API_VERSION.
DEFAULT_API_VERSION = "2026-07-29.preview"


def _secret_key() -> str:
    return os.environ.get("STRIPE_SECRET_KEY", "").strip()


def _api_version() -> str:
    return os.environ.get("STRIPE_API_VERSION", DEFAULT_API_VERSION).strip()


def _pi_network() -> str:
    # Stripe PaymentIntent transaction_verification network label (e.g. "base").
    return os.environ.get("STRIPE_PI_NETWORK", "base").strip()


def enabled() -> bool:
    return bool(_secret_key())


def encode_form(data: dict, parent: str = "") -> list[tuple[str, str]]:
    """Flatten a nested dict/list into Stripe's bracketed form-encoding.

    {"a": {"b": "c"}} -> [("a[b]", "c")]
    {"a": ["x", "y"]} -> [("a[0]", "x"), ("a[1]", "y")]
    """
    pairs: list[tuple[str, str]] = []
    for key, value in data.items():
        full = f"{parent}[{key}]" if parent else str(key)
        if isinstance(value, dict):
            pairs.extend(encode_form(value, full))
        elif isinstance(value, (list, tuple)):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    pairs.extend(encode_form(item, f"{full}[{i}]"))
                else:
                    pairs.append((f"{full}[{i}]", str(item)))
        elif isinstance(value, bool):
            pairs.append((full, "true" if value else "false"))
        else:
            pairs.append((full, str(value)))
    return pairs


def atomic_usdc_to_cents(amount_atomic: str | int | None) -> int:
    """USDC atomic units (6 decimals) -> USD cents. 10000 atomic = 1 cent."""
    if amount_atomic is None:
        return 0
    return round(int(amount_atomic) / 10000)


def build_payment_intent_params(tx_hash: str, amount_atomic: str | int) -> dict[str, Any]:
    """Build the PaymentIntent params for transaction_verification mode."""
    return {
        "amount": atomic_usdc_to_cents(amount_atomic),
        "currency": "usd",
        "confirm": "true",
        "payment_method_data": {"type": "crypto"},
        "allowed_payment_method_types": ["crypto"],
        "payment_method_options": {
            "crypto": {
                "mode": "transaction_verification",
                "transaction_verification_options": {
                    "network": _pi_network(),
                    "transaction_hash": tx_hash,
                },
            }
        },
    }


# Type of an injectable POST function, for tests: (url, data, headers, auth, idem) -> dict
Poster = Callable[[str, list[tuple[str, str]], dict, tuple[str, str]], dict]


def _default_post(
    url: str, data: list[tuple[str, str]], headers: dict, auth: tuple[str, str]
) -> dict:
    resp = httpx.post(url, data=data, headers=headers, auth=auth, timeout=30)
    resp.raise_for_status()
    return resp.json()


def record_payment(
    tx_hash: str | None,
    amount_atomic: str | int | None,
    *,
    success: bool = True,
    post: Poster | None = None,
) -> str | None:
    """Record one settled payment as a Stripe PaymentIntent. Returns the PI id or None.

    Safe to call unconditionally: no-ops when Stripe is not configured, when the
    settlement was not successful, when there is no tx hash, or when the amount
    rounds to less than one cent. Never raises.
    """
    try:
        if not enabled():
            return None
        if not success or not tx_hash:
            return None
        cents = atomic_usdc_to_cents(amount_atomic)
        if cents < 1:
            log.info("stripe: amount %s rounds below 1 cent; not recording", amount_atomic)
            return None

        params = build_payment_intent_params(tx_hash, amount_atomic)
        data = encode_form(params)
        headers = {
            "Stripe-Version": _api_version(),
            # Idempotent on the tx hash: a duplicate settlement records once.
            "Idempotency-Key": tx_hash,
        }
        poster = post or _default_post
        result = poster(f"{STRIPE_API}/payment_intents", data, headers, (_secret_key(), ""))
        pi_id = result.get("id")
        log.info("stripe: recorded PaymentIntent %s for tx %s (%d cents)", pi_id, tx_hash, cents)
        return pi_id
    except Exception as e:  # never propagate into the after-settle hook
        log.warning("stripe: failed to record payment for tx %s: %s", tx_hash, e)
        return None
