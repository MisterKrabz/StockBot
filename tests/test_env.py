from config.settings import (
    ALPACA_API_KEY_ID,
    FRED_API_KEY,
    SEC_USER_AGENT,
)

def test_env_loaded():
    assert ALPACA_API_KEY_ID is not None
    assert FRED_API_KEY is not None
    assert SEC_USER_AGENT is not None
