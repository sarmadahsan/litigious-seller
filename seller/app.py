"""litigious-seller FastAPI app.

This file wires the official x402 payment middleware and mounts the honest
support endpoints (ledger, published contact, health). The two paid routes that
give this seller its character are left as marked stubs for you to implement:

    GET /intel/{ticker}          -- the double-charge route
    GET /dossier/{ticker}        -- the charge-without-delivery route
    GET /dossier/status/{id}     -- the status route the dossier route refers to

Everything the routes need is already here:
  * ``ledger.record(...)`` to write a row to the seller's books
  * ``CONFIG`` for pay_to / support contact
  * ``server`` and ``ROUTES`` already registered with the middleware

Your route handlers decide what to return and what to record. See
docs/billguard-detection-and-dispute.md for the behavior each route is meant
to exhibit and how BillGuard is expected to catch it.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from x402 import x402ResourceServer
from x402.http import FacilitatorConfig, HTTPFacilitatorClient
from x402.http.middleware.fastapi import payment_middleware
from x402.mechanisms.evm.exact import ExactEvmServerScheme

from .config import NETWORK, load_config
from .ledger import ledger

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("litigious-seller")

CONFIG = load_config()

# --- x402 resource server (official SDK, no BillGuard anything) -------------
_facilitator = HTTPFacilitatorClient(FacilitatorConfig(url=CONFIG.facilitator_url))
server = x402ResourceServer(_facilitator)
server.register(NETWORK, ExactEvmServerScheme())

# Payment-gated routes. Price/payTo/network are honest config; the middleware
# enforces payment before the handler runs. Handler *behavior* is yours.
ROUTES = {
    "GET /intel/*": {
        "accepts": {
            "scheme": "exact",
            "payTo": CONFIG.pay_to,
            "price": "$0.50",
            "network": NETWORK,
        },
        "description": (
            f"Equity intel report. Support: {CONFIG.support_email} "
            f"/ {CONFIG.support_phone}"
        ),
    },
    "GET /dossier/*": {
        "accepts": {
            "scheme": "exact",
            "payTo": CONFIG.pay_to,
            "price": "$0.75",
            "network": NETWORK,
        },
        "description": (
            f"Company dossier (async). Support: {CONFIG.support_email} "
            f"/ {CONFIG.support_phone}"
        ),
    },
}

app = FastAPI(title=CONFIG.seller_name)

# Build the payment middleware once. sync_facilitator_on_start=False avoids a
# network call to the facilitator at construction (keeps import/tests offline);
# verification and settlement still use the facilitator at request time.
_payment_mw = payment_middleware(ROUTES, server, sync_facilitator_on_start=False)


@app.middleware("http")
async def x402_mw(request: Request, call_next):
    return await _payment_mw(request, call_next)


# ============================================================================
# Honest support endpoints (implemented)
# ============================================================================


@app.get("/")
async def health() -> dict:
    return {"service": CONFIG.seller_name, "ok": True}


@app.get("/.well-known/x402-seller.json")
async def seller_contact() -> dict:
    """Published contact. BillGuard reads this to address a dispute."""
    return {
        "name": CONFIG.seller_name,
        "support_email": CONFIG.support_email,
        "support_phone": CONFIG.support_phone,
        "network": NETWORK,
        "pay_to": CONFIG.pay_to,
    }


@app.get("/ledger", response_class=HTMLResponse)
async def ledger_page() -> str:
    rows = ledger.all()
    summary = ledger.by_payer()
    body = [
        "<!doctype html><meta charset=utf-8>",
        f"<title>{CONFIG.seller_name} ledger</title>",
        "<style>body{font:14px system-ui;margin:2rem}"
        "table{border-collapse:collapse}td,th{border:1px solid #ccc;padding:4px 8px}"
        ".no{color:#b00}.yes{color:#070}</style>",
        f"<h1>{CONFIG.seller_name} &mdash; settlement ledger</h1>",
        "<h2>By payer</h2><table><tr><th>payer</th><th>charges</th>"
        "<th>deliveries</th><th>routes</th></tr>",
    ]
    for payer, s in sorted(summary.items()):
        body.append(
            f"<tr><td>{payer}</td><td>{s['charges']}</td>"
            f"<td>{s['deliveries']}</td><td>{', '.join(s['routes'])}</td></tr>"
        )
    body.append("</table><h2>Rows</h2><table><tr><th>time</th><th>payer</th>"
                "<th>route</th><th>amount</th><th>delivered</th><th>tx</th>"
                "<th>note</th></tr>")
    for r in rows:
        d = r.as_dict()
        cls = "yes" if r.delivered else "no"
        body.append(
            f"<tr><td>{d['ts_iso']}</td><td>{d['payer']}</td><td>{d['route']}</td>"
            f"<td>{d['amount'] or ''}</td><td class={cls}>{r.delivered}</td>"
            f"<td>{d['tx_hash'] or ''}</td><td>{d['note']}</td></tr>"
        )
    body.append("</table>")
    return "".join(body)


@app.get("/ledger.json")
async def ledger_json() -> JSONResponse:
    return JSONResponse(
        {
            "by_payer": ledger.by_payer(),
            "rows": [r.as_dict() for r in ledger.all()],
        }
    )


# ============================================================================
# Paid routes -- YOU IMPLEMENT THESE
# ============================================================================
# The middleware above already requires payment for GET /intel/* and
# GET /dossier/*. Add the handlers below. Use ledger.record(payer=..., route=...,
# tx_hash=..., amount=..., delivered=..., note=...) to write to the books.
#
#   @app.get("/intel/{ticker}")
#   async def intel(ticker: str, request: Request): ...
#
#   @app.get("/dossier/{ticker}")
#   async def dossier(ticker: str, request: Request): ...
#
#   @app.get("/dossier/status/{order_id}")
#   async def dossier_status(order_id: str): ...
#
# request.state.payment_payload and request.state.payment_requirements are set
# by the middleware once payment verifies, so the payer address is available to
# your handler. See docs/billguard-detection-and-dispute.md.
