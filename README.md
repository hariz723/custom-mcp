# Autonomous Playwright MCP Server 🚀

A custom [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server built with **Playwright**, **FastMCP / MCPServer**, and **Self-Healing LLM runtime execution**.

Unlike basic Playwright MCP wrappers that only provide low-level browser primitives, this server:
1. **Automatically scrapes page metadata**: Meta tags (SEO, OpenGraph, Twitter), headings hierarchy, and a structured map of interactive elements (inputs, buttons, forms, links) with robust CSS/XPath selectors.
2. **Automatically synthesizes Playwright Python automation code**: Uses an LLM to generate targeted execution scripts for high-level user tasks.
3. **Executes code live in the runtime**: Runs against active Playwright pages within the container or host environment.
4. **Self-Heals execution failures**: If an element selector fails, times out, or page state changes, the server catches the runtime error, re-inspects the DOM, prompts the LLM to fix the script, and retries automatically until success.
5. **Modern Packaging**: Fully managed via `pyproject.toml` (PEP 517/621) with zero bloated dependencies.

---

## Architecture Overview

```
User / AI Client (Antigravity / Claude / Cursor)
       │
       ▼  MCP (Streamable HTTP / Stdio)
┌────────────────────────────────────────────────────────┐
│  Playwright MCP Server                                 │
│                                                        │
│  ┌─────────────────┐       ┌────────────────────────┐  │
│  │ metadata.py     │ ───►  │ llm.py (Code Gen)      │  │
│  │ (Scrapes DOM)   │       └──────────┬─────────────┘  │
│  └─────────────────┘                  │                │
│                                       ▼                │
│                            ┌────────────────────────┐  │
│                            │ executor.py            │  │
│                            │ (Runs async Playwright)│  │
│                            └──────────┬─────────────┘  │
│                                       │ (On Error)     │
│                                       ▼                │
│                            ┌────────────────────────┐  │
│                            │ Self-Healing Loop      │  │
│                            │ (Diagnose & Repair)    │  │
│                            └────────────────────────┘  │
│                                       │                │
│  ┌────────────────────────────────────▼─────────────┐  │
│  │ browser.py (Chromium / Viewport / Screenshots)   │  │
│  └──────────────────────────────────────────────────┘  │
└──────────────────────────┬─────────────────────────────┘
                           │ Outputs
                           ▼
                  ./output/screenshots/ & ./output/pdfs/
```

---

## Option 1: Setup with Docker & Docker Compose (Recommended)

### 1. Setup Environment
```bash
make setup
```
*(Or manually copy `.env.example` to `.env` and create `output/screenshots` and `output/pdfs`)*.

Add your LLM API key in `.env`:
```env
LLM_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=your_gemini_api_key_here
```

### 2. Build and Start Service
```bash
make up
```
*(Or `docker compose up -d --build`)*.

The server runs on port `8000` exposing the Streamable HTTP endpoint:
```
http://localhost:8000/mcp
```

### 3. Check Logs or Health
```bash
make logs
make test-mcp
```

To stop the container:
```bash
make down
```

---

## Option 2: Setup Directly on Host (Without Docker)

You can run the MCP server natively on Linux, macOS, or Windows using Python 3.11+.

### Prerequisites
- Python `>= 3.11`
- `uv` (recommended for blazing-fast package management) or standard `pip`

### Step 1: Clone and Navigate to Directory
```bash
cd /home/hari/projects/custom-mcp
```

### Step 2: Create and Activate Virtual Environment
Using `uv`:
```bash
uv venv
source .venv/bin/activate
```
*(Or with standard Python: `python3 -m venv .venv && source .venv/bin/activate`)*

### Step 3: Install Package Dependencies
Install the package in editable mode using `pyproject.toml`:
```bash
uv pip install -e .
```
*(Or with pip: `pip install -e .`)*

### Step 4: Install Chromium Browser Driver
```bash
playwright install chromium
```
*(On Linux, if any OS library is missing: `playwright install-deps chromium`)*

### Step 5: Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
mkdir -p output/screenshots output/pdfs
```

Edit `.env` with your API key:
```env
# Choose your LLM model:
LLM_MODEL=gemini/gemini-2.5-flash
GEMINI_API_KEY=your_gemini_api_key_here

# Or for OpenAI:
# LLM_MODEL=gpt-4o-mini
# OPENAI_API_KEY=your_openai_api_key_here

# Or for local Ollama:
# LLM_MODEL=llama3.2
# OLLAMA_API_BASE=http://localhost:11434
```

### Step 6: Start the Server

#### Mode A: Streamable HTTP (Default, recommended for Antigravity & Web Clients)
```bash
playwright-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```
The server will listen at:
```
http://127.0.0.1:8000/mcp
```

#### Mode B: Stdio Transport (Direct CLI / Claude Desktop)
```bash
playwright-mcp --transport stdio
```

---

## Connecting to AI Clients

### 1. Google Antigravity
Open `~/.gemini/config/mcp_config.json` and add:

**When running via Streamable HTTP (Docker or Local):**
```json
{
  "mcpServers": {
    "playwright-custom": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**When running directly via Local Python Stdio (No Docker):**
```json
{
  "mcpServers": {
    "playwright-custom": {
      "command": "/home/hari/projects/custom-mcp/.venv/bin/python",
      "args": ["/home/hari/projects/custom-mcp/server.py", "--transport", "stdio"],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here"
      }
    }
  }
}
```

---

### 2. Claude Desktop

In `claude_desktop_config.json`:

**Without Docker (Local Python):**
```json
{
  "mcpServers": {
    "playwright-custom": {
      "command": "/home/hari/projects/custom-mcp/.venv/bin/python",
      "args": ["/home/hari/projects/custom-mcp/server.py", "--transport", "stdio"],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here"
      }
    }
  }
}
```

**With Docker:**
```json
{
  "mcpServers": {
    "playwright-custom": {
      "command": "docker",
      "args": [
        "compose",
        "-f",
        "/home/hari/projects/custom-mcp/docker-compose.yml",
        "run",
        "--rm",
        "-i",
        "-e",
        "MCP_TRANSPORT=stdio",
        "playwright-mcp"
      ]
    }
  }
}
```

---

### 3. LM Studio

You can use LM Studio with this MCP server in **two different ways**:
- **Integration A**: Use LM Studio as the **MCP Client** (control the browser from LM Studio chat).
- **Integration B**: Use LM Studio as the **Local LLM Brain** (run code generation and self-healing 100% offline without cloud API keys).

#### Integration A: Using LM Studio as the MCP Client (Chat & Tools)

LM Studio (v0.3.0+) supports the Model Context Protocol natively.

1. Open LM Studio.
2. Go to **Settings** > **Model Context Protocol (MCP)** (or the **Tools / Program** icon in the left sidebar).
3. Click **Edit `mcp.json`** (or open `~/.cache/lm-studio/mcp.json` on Linux / `~/.lmstudio/mcp.json` on macOS/Windows).
4. Add the server definition:

**Option 1: Using Local Python (Without Docker)**
```json
{
  "mcpServers": {
    "playwright-custom": {
      "command": "/home/hari/projects/custom-mcp/.venv/bin/python",
      "args": ["/home/hari/projects/custom-mcp/server.py", "--transport", "stdio"],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here"
      }
    }
  }
}
```

**Option 2: Using Docker**
```json
{
  "mcpServers": {
    "playwright-custom": {
      "command": "docker",
      "args": [
        "compose",
        "-f",
        "/home/hari/projects/custom-mcp/docker-compose.yml",
        "run",
        "--rm",
        "-i",
        "-e",
        "MCP_TRANSPORT=stdio",
        "playwright-mcp"
      ]
    }
  }
}
```

5. Save the file. LM Studio will discover all `browser_*` tools! In your chat, enable tool calling and prompt:
   > *"Navigate to https://news.ycombinator.com and capture a full-page screenshot."*

---

#### Integration B: Using LM Studio as the Local LLM Brain (100% Offline Self-Healing)

You can run the Playwright code generation and runtime self-healing engine **completely offline** with local models (e.g. `Qwen 2.5 Coder 7B/14B` or `Llama 3.2`) powered by LM Studio.

1. In LM Studio, download a coding model (Recommended: `qwen2.5-coder-7b-instruct` or `deepseek-coder-6.7b`).
2. Go to the **Developer / Local Server (`<->`)** tab in LM Studio.
3. Load the model and click **Start Server** (default port: `1234`).
4. Configure your `.env` in `custom-mcp`:

**When running the MCP server locally (without Docker):**
```env
LM_STUDIO_API_BASE=http://localhost:1234/v1
LLM_MODEL=qwen2.5-coder-7b-instruct
```

**When running the MCP server inside Docker:**
```env
LM_STUDIO_API_BASE=http://host.docker.internal:1234/v1
LLM_MODEL=qwen2.5-coder-7b-instruct
```

5. Start the server (`make up` or `playwright-mcp`). All DOM analysis, Playwright code generation, and error self-healing will run entirely on your local GPU/CPU!

---

## MCP Tools Reference

### Autonomous & Self-Healing Tools
| Tool | Description |
| :--- | :--- |
| `browser_auto_task` | Autonomous end-to-end task execution: scrapes DOM, generates Playwright code, executes in runtime, and automatically heals errors via LLM. |
| `browser_scrape_metadata` | Extracts full page metadata, SEO tags, headings, and interactive elements map (inputs, buttons, links, selectors). |
| `browser_execute_script` | Runs custom Playwright Python snippet (`async def execute(page, context):`) with optional automatic self-healing. |

### Browser Controls
| Tool | Description |
| :--- | :--- |
| `browser_navigate` | Navigates to a URL with configurable `wait_until` conditions. |
| `browser_screenshot` | Captures full-page or element screenshot and saves to `./output/screenshots/`. |
| `browser_click` | Clicks elements matching CSS or XPath selector. |
| `browser_fill` | Fills form fields or input elements with text. |
| `browser_press_key` | Presses keyboard keys (`Enter`, `Tab`, `ArrowDown`, etc.). |
| `browser_get_text` | Returns clean visible text from page or element. |
| `browser_get_html` | Returns clean HTML (stripping script/style/svg to save LLM tokens). |
| `browser_evaluate` | Evaluates JavaScript expression in browser context. |
| `browser_pdf` | Generates a PDF of current page and saves to `./output/pdfs/`. |
| `browser_reset` | Resets active page and context (clears cookies/cache). |
| `browser_close` | Shuts down browser processes cleanly. |

---

## Makefile Targets Reference

| Target | Description |
| :--- | :--- |
| `make help` | Show help with all available commands |
| `make setup` | Setup local `.env` and output folders |
| `make build` | Build Docker container |
| `make up` | Start MCP server container in background |
| `make down` | Stop container |
| `make restart` | Restart container |
| `make logs` | Tail real-time logs |
| `make status` | Check container health and status |
| `make run-stdio` | Run in Stdio mode via Docker |
| `make test-mcp` | Test if HTTP `/mcp` endpoint is responding |
| `make clean` | Clean build and cache files |
