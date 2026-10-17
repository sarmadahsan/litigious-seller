import os
import sys

os.environ.setdefault("SELLER_PAY_TO", "0x1111111111111111111111111111111111111111")
os.environ.setdefault("SUPPORT_EMAIL", "disputes@meridian-intel.example")
os.environ.setdefault("SUPPORT_PHONE", "+15555550123")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
