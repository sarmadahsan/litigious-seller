"""Check the seller wallet config and print faucet links.

Run: uv run python scripts/setup_wallet.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from seller.config import NETWORK, load_config  # noqa: E402

FAUCETS = [
    ("Base Sepolia ETH (gas, only needed for a local facilitator)",
     "https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet"),
    ("Base Sepolia USDC (test)",
     "https://faucet.circle.com/"),
]


def main() -> int:
    cfg = load_config()
    print(f"Seller     : {cfg.seller_name}")
    print(f"Network    : {NETWORK} (Base Sepolia)")
    print(f"pay_to     : {cfg.pay_to}")
    print(f"facilitator: {cfg.facilitator_mode} -> {cfg.facilitator_url}")
    print(f"support    : {cfg.support_email} / {cfg.support_phone}")
    print()
    if cfg.pay_to == "0x" + "0" * 40:
        print("WARNING: SELLER_PAY_TO is unset. Set it in .env before the demo.")
    print("Faucets:")
    for name, url in FAUCETS:
        print(f"  - {name}\n      {url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
