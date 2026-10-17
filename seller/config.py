"""Environment-backed configuration for the seller."""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional at runtime
    pass

# Base Sepolia. The honest sellers in the BillGuard demo use the same network.
NETWORK = "eip155:84532"


@dataclass(frozen=True)
class Config:
    pay_to: str
    facilitator_mode: str  # "remote"
    facilitator_url: str
    support_email: str
    support_phone: str
    port: int
    stripe_secret_key: str
    stripe_api_version: str
    stripe_pi_network: str

    @property
    def seller_name(self) -> str:
        return "Meridian Intel"

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key)


def load_config() -> Config:
    pay_to = os.environ.get("SELLER_PAY_TO", "").strip()
    if not pay_to:
        # Not fatal for import/tests; app startup warns. Scripts check explicitly.
        pay_to = "0x0000000000000000000000000000000000000000"
    return Config(
        pay_to=pay_to,
        facilitator_mode=os.environ.get("SELLER_FACILITATOR", "remote").strip().lower(),
        facilitator_url=os.environ.get(
            "FACILITATOR_URL", "https://x402.org/facilitator"
        ).strip(),
        support_email=os.environ.get(
            "SUPPORT_EMAIL", "support@litigious-seller.example"
        ).strip(),
        support_phone=os.environ.get("SUPPORT_PHONE", "+15555550100").strip(),
        port=int(os.environ.get("PORT", "8402")),
        stripe_secret_key=os.environ.get("STRIPE_SECRET_KEY", "").strip(),
        stripe_api_version=os.environ.get("STRIPE_API_VERSION", "2026-07-29.preview").strip(),
        stripe_pi_network=os.environ.get("STRIPE_PI_NETWORK", "base").strip(),
    )
