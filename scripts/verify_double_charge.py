"""Prove, from the chain, how many times a buyer actually paid a seller.

This is the detection/measurement side. It does not call the seller and does not
trust any seller response. It reads USDC Transfer logs on Base Sepolia and counts
transfers from one buyer wallet to the seller's payTo in a block window.

If a single logical purchase produced more than one transfer, the buyer was
charged more than once -- a double charge proven on-chain. This is exactly the
check a buyer-protection layer must do instead of believing an HTTP "payment
failed" response.

Run:
  uv run python scripts/verify_double_charge.py \
      --buyer  0xYOURBUYER \
      --pay-to 0xSELLERPAYTO \
      --from-block 12345678

Flags:
  --rpc         Base Sepolia RPC (default https://sepolia.base.org)
  --usdc        USDC contract (default Base Sepolia test USDC)
  --from-block  start block (default: latest - 5000)
  --to-block    end block (default: latest)
"""

from __future__ import annotations

import argparse

from web3 import Web3

# Base Sepolia test USDC, per the BillGuard design.
DEFAULT_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
DEFAULT_RPC = "https://sepolia.base.org"

# keccak("Transfer(address,address,uint256)")
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


def _topic_addr(addr: str) -> str:
    return "0x" + "0" * 24 + Web3.to_checksum_address(addr)[2:].lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buyer", required=True, help="buyer wallet (payer)")
    ap.add_argument("--pay-to", required=True, help="seller payTo address")
    ap.add_argument("--usdc", default=DEFAULT_USDC)
    ap.add_argument("--rpc", default=DEFAULT_RPC)
    ap.add_argument("--from-block", type=int, default=None)
    ap.add_argument("--to-block", type=int, default=None)
    ap.add_argument("--chunk", type=int, default=8,
                    help="max blocks per getLogs request (public RPCs limit the range)")
    args = ap.parse_args()

    w3 = Web3(Web3.HTTPProvider(args.rpc))
    if not w3.is_connected():
        print(f"ERROR: cannot reach RPC {args.rpc}")
        return 2

    latest = w3.eth.block_number
    # Default to a modest lookback; public RPCs reject wide getLogs ranges.
    from_block = args.from_block if args.from_block is not None else max(0, latest - 500)
    to_block = args.to_block if args.to_block is not None else latest

    topics = [
        TRANSFER_TOPIC,
        _topic_addr(args.buyer),   # indexed from
        _topic_addr(args.pay_to),  # indexed to
    ]
    usdc = Web3.to_checksum_address(args.usdc)

    def get_logs_range(lo: int, hi: int) -> list:
        """getLogs over [lo, hi], splitting on range-limit errors from the RPC."""
        try:
            return w3.eth.get_logs(
                {"fromBlock": lo, "toBlock": hi, "address": usdc, "topics": topics}
            )
        except Exception:
            if lo >= hi:
                raise
            mid = (lo + hi) // 2
            return get_logs_range(lo, mid) + get_logs_range(mid + 1, hi)

    # Walk the window in fixed chunks, with recursive splitting as a fallback.
    logs = []
    step = max(1, args.chunk)
    lo = from_block
    while lo <= to_block:
        hi = min(lo + step - 1, to_block)
        logs.extend(get_logs_range(lo, hi))
        lo = hi + 1

    print(f"USDC {args.usdc} on {args.rpc}")
    print(f"buyer {args.buyer} -> payTo {args.pay_to}")
    print(f"blocks {from_block}..{to_block}")
    print(f"transfers found: {len(logs)}")
    total = 0
    for i, log in enumerate(logs, 1):
        # Transfer value is the 32-byte data word; Web3 may hand back bytes or hexstr.
        raw = log["data"]
        if isinstance(raw, (bytes, bytearray)):
            amount = int.from_bytes(raw, "big")
        else:
            amount = int(raw, 16)
        total += amount
        print(f"  {i}. block {log['blockNumber']} tx {log['transactionHash'].hex()} "
              f"amount {amount / 1e6:.6f} USDC")

    print()
    if len(logs) <= 1:
        print("RESULT: no double charge detected in this window "
              "(0 or 1 transfer).")
    else:
        print(f"RESULT: DOUBLE CHARGE PROVEN -- {len(logs)} separate on-chain "
              f"transfers, total {total / 1e6:.6f} USDC, for this buyer/seller "
              f"pair. The seller's HTTP responses are irrelevant to this count.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
