"""The seller's own books.

Honest bookkeeping: every time a route decides something happened to a payer,
it records a row here. The ``/ledger`` page renders these rows. This module is
deliberately neutral; it does not know or care whether a given row represents
fair dealing. It just records what the route tells it.

The row's ``delivered`` flag and ``note`` are set by the route handler, so the
ledger reflects whatever the seller's routes choose to report.
"""

from __future__ import annotations

import threading
import time
from dataclasses import asdict, dataclass, field


@dataclass
class Entry:
    ts: float
    payer: str
    route: str
    tx_hash: str | None
    amount: str | None
    delivered: bool
    note: str = ""

    def as_dict(self) -> dict:
        d = asdict(self)
        d["ts_iso"] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.ts))
        return d


class Ledger:
    def __init__(self) -> None:
        self._rows: list[Entry] = []
        self._lock = threading.Lock()

    def record(
        self,
        *,
        payer: str | None,
        route: str,
        tx_hash: str | None = None,
        amount: str | None = None,
        delivered: bool = False,
        note: str = "",
    ) -> Entry:
        entry = Entry(
            ts=time.time(),
            payer=(payer or "unknown").lower(),
            route=route,
            tx_hash=tx_hash,
            amount=amount,
            delivered=delivered,
            note=note,
        )
        with self._lock:
            self._rows.append(entry)
        return entry

    def all(self) -> list[Entry]:
        with self._lock:
            return list(self._rows)

    def by_payer(self) -> dict[str, dict]:
        """Per-wallet rollup: how many charges, how many deliveries."""
        summary: dict[str, dict] = {}
        for row in self.all():
            s = summary.setdefault(
                row.payer, {"charges": 0, "deliveries": 0, "routes": set()}
            )
            s["charges"] += 1
            s["deliveries"] += 1 if row.delivered else 0
            s["routes"].add(row.route)
        for s in summary.values():
            s["routes"] = sorted(s["routes"])
        return summary

    def reset(self) -> None:
        with self._lock:
            self._rows.clear()


# Module-level singleton shared by the app.
ledger = Ledger()
