"""A naive x402-paying MCP server, the UNPROTECTED buyer side.

This is the "agent as customer" with no buyer protections. Claude Desktop (or any
MCP client) connects to it over stdio and calls a tool; the tool pays the seller
via x402 and returns whatever the seller said, verbatim. It has no spending
mandate, no reconciliation, and no duplicate guard, so if the seller reports a
payment as failed, the tool simply surfaces that message and Claude, like any
naive agent, may call the tool again and pay again. That is the vulnerability the
demo shows.

Environment:
  SELLER_URL          base URL of the seller, e.g. https://xxxx.trycloudflare.com
  BUYER_KEY_SEPOLIA   funded Base Sepolia private key (the buyer wallet)
  BUYER_TIMEOUT_S     optional, per-request timeout (default 60)

Run (stdio):  uv run python -m buyer.server
"""

from __future__ import annotations

import json
import os

import httpx
from eth_account import Account
from mcp.server.fastmcp import FastMCP

from x402 import x402Client
from x402.http.clients import x402_httpx_transport
from x402.mechanisms.evm.exact import ExactEvmScheme
from x402.mechanisms.evm.signers import EthAccountSigner

mcp = FastMCP("naive-x402-buyer")


def _seller_url() -> str:
    url = os.environ.get("SELLER_URL", "http://localhost:8402").strip().rstrip("/")
    return url


def _timeout() -> float:
    return float(os.environ.get("BUYER_TIMEOUT_S", "60"))


def _build_client() -> x402Client:
    key = os.environ.get("BUYER_KEY_SEPOLIA", "").strip()
    if not key:
        raise RuntimeError("BUYER_KEY_SEPOLIA is not set")
    account = Account.from_key(key)
    client = x402Client()
    client.register("eip155:*", ExactEvmScheme(EthAccountSigner(account)))
    # No mandate: a bare buyer does not cap per-payment spend. This is the point.
    client.set_spend_controls({"max_amount_per_payment": False})
    return client


async def _paid_get(path: str) -> str:
    """Do one x402-paid GET and return a human-readable result string.

    One call == one payment attempt. On a 200 the resource is returned. On a 402
    the seller's message is surfaced verbatim (it may claim the payment failed
    and ask to retry); this tool does not reconcile or block a retry.
    """
    url = f"{_seller_url()}{path}"
    client = _build_client()
    transport = x402_httpx_transport(client)
    async with httpx.AsyncClient(transport=transport, timeout=_timeout()) as http:
        resp = await http.get(url)
    status = resp.status_code
    ctype = resp.headers.get("content-type", "")
    body = resp.text
    try:
        parsed = resp.json()
        body = json.dumps(parsed, indent=2)
    except Exception:
        pass
    if status == 200:
        return f"Success (HTTP 200). Paid and received:\n{body}"
    if status == 402:
        return (
            f"The seller returned HTTP 402.\n{body}\n\n"
            f"(A payment attempt was made for this request.)"
        )
    return f"HTTP {status} ({ctype}):\n{body}"


@mcp.tool()
async def fetch_intel(ticker: str) -> str:
    """Buy an equity intel report for a ticker from the data seller (costs USDC)."""
    return await _paid_get(f"/intel/{ticker}")


@mcp.tool()
async def fetch_dossier(ticker: str) -> str:
    """Order a company dossier for a ticker from the data seller (costs USDC)."""
    return await _paid_get(f"/dossier/{ticker}")


@mcp.tool()
async def check_order(order_id: str) -> str:
    """Check the status of a previously ordered dossier (free)."""
    url = f"{_seller_url()}/order/{order_id}"
    async with httpx.AsyncClient(timeout=_timeout()) as http:
        resp = await http.get(url)
    try:
        return json.dumps(resp.json(), indent=2)
    except Exception:
        return f"HTTP {resp.status_code}: {resp.text}"


if __name__ == "__main__":
    mcp.run()
