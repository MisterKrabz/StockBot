import os
from dotenv import load_dotenv

load_dotenv()

ALPACA_API_KEY_ID = os.getenv("ALPACA_API_KEY_ID")
ALPACA_API_SECRET_KEY = os.getenv("ALPACA_API_SECRET_KEY")
FRED_API_KEY = os.getenv("FRED_API_KEY")
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT")

# Safety checks (fail fast)
required = {
    "ALPACA_API_KEY_ID": ALPACA_API_KEY_ID,
    "ALPACA_API_SECRET_KEY": ALPACA_API_SECRET_KEY,
    "FRED_API_KEY": FRED_API_KEY,
    "SEC_USER_AGENT": SEC_USER_AGENT,
}

missing = [k for k, v in required.items() if not v]
if missing:
    raise RuntimeError(f"Missing required environment variables: {missing}")
