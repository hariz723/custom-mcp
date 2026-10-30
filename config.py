import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Server Settings
SERVER_NAME = os.getenv("MCP_SERVER_NAME", "custom-playwright")
TRANSPORT = os.getenv("MCP_TRANSPORT", "streamable-http").lower()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Browser Settings
HEADLESS = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
VIEWPORT_WIDTH = int(os.getenv("VIEWPORT_WIDTH", "1280"))
VIEWPORT_HEIGHT = int(os.getenv("VIEWPORT_HEIGHT", "720"))
DEFAULT_TIMEOUT_MS = int(os.getenv("DEFAULT_TIMEOUT_MS", "30000"))

# LLM & Self-Healing Settings
# Supported models: 'gemini/gemini-2.5-flash', 'gpt-4o', 'gpt-4o-mini', 'claude-3-5-sonnet-20241022', 'ollama/llama3.2', etc.
LLM_MODEL = os.getenv("LLM_MODEL", "gemini/gemini-2.5-flash")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Output Paths
BASE_OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./output")).resolve()
SCREENSHOTS_DIR = BASE_OUTPUT_DIR / "screenshots"
PDFS_DIR = BASE_OUTPUT_DIR / "pdfs"

# Ensure output directories exist
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
PDFS_DIR.mkdir(parents=True, exist_ok=True)
