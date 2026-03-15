# config.py — Loads environment variables from .env file.
# All other modules import keys from here.

import os
from dotenv import load_dotenv

load_dotenv()

SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

def validate():
    missing = []
    if not SERPAPI_KEY:
        missing.append("SERPAPI_KEY")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Copy .env.example to .env and fill in your keys."
        )
