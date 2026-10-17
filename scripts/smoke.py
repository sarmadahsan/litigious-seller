"""Smoke-test a route by paying it with a plain x402 client.

This is an ORDINARY x402 buyer. It has no buyer protections; it is the
"unprotected agent" baseline. With --retries it simply retries on a 402,
which is what any naive agent does when a seller says a payment failed.

Run:
  uv run python scripts/smoke.py --url http://localhost:8402/intel/AAPL --retries 2

Requires BUYER_KEY_SEPOLIA in the environment (a funded Base Sepolia test key).
"""

from __future__ import annotations

import argparse
import asyncio
import os

import httpx
from eth_account import Account

from x402 import x402Client
from x402.http.clients import x402_httpx_transport
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.mechanisms.evm.signers import EthAccountSigner


def build_client() -> x402Client:
    key = os.environ["BUYER_KEY_SEPOLIA"]
    account = Account.from_key(key)
    client = x402Client()
    client.register("eip155:*", ExactEvmScheme(EthAccountSigner(account)))
    # BillGuard owns the mandate in the real system; the bare client does not cap.
    client.set_spend_controls({"max_amount_per_payment": False})
    return client


async def run(url: str, retries: int) -> None:
    client = build_client()
    transport = x402_httpx_transport(client)
    async with httpx.AsyncClient(transport=transport, timeout=60) as http:
        attempt = 0
        while True:
            attempt += 1
            resp = await http.get(url)
            print(f"attempt {attempt}: HTTP {resp.status_code}")
            tx = resp.headers.get("PAYMENT-RESPONSE")
            if tx:
                print(f"  settlement header: {tx[:80]}...")
            ctype = resp.headers.get("content-type", "")
            if "json" in ctype:
                print(f"  body: {resp.text[:300]}")
            if resp.status_code != 402 or attempt > retries:
                break
            print("  got 402 'payment failed' -> retrying (naive agent behavior)")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--retries", type=int, default=0,
                   help="how many times to retry on a 402")
    args = p.parse_args()
    asyncio.run(run(args.url, args.retries))


if __name__ == "__main__":
    main()
