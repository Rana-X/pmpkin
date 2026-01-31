"""Configuration module - loads environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from parent directory's .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Required environment variables
REQUIRED_VARS = ["OPENAI_API_KEY", "REDUCTO_API_KEY"]

def _validate_env_vars():
    missing = [var for var in REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            f"Ensure {env_path} exists and contains all required variables."
        )

_validate_env_vars()

OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]
REDUCTO_API_KEY = os.environ["REDUCTO_API_KEY"]
