import json
import logging
import os
import re
from typing import Any

from openai import AsyncOpenAI

from config import LLM_MODEL, LLM_TEMPERATURE

logger = logging.getLogger(__name__)


def extract_python_code(raw_response: str) -> str:
    """Extracts clean executable Python code from LLM response."""
    pattern = r"```(?:python)?\s*([\s\S]*?)```"
    match = re.search(pattern, raw_response, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return raw_response.strip()


def get_llm_client() -> tuple[AsyncOpenAI, str]:
    """Returns an AsyncOpenAI client and model name configured for the detected provider."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    ollama_base = os.getenv("OLLAMA_API_BASE")
    lm_studio_base = os.getenv("LM_STUDIO_API_BASE")
    custom_base = os.getenv("OPENAI_API_BASE")

    model = LLM_MODEL

    # 1. LM Studio Local Inference
    if lm_studio_base:
        base_url = lm_studio_base if lm_studio_base.endswith("/v1") else f"{lm_studio_base}/v1"
        client = AsyncOpenAI(api_key="lm-studio", base_url=base_url)
        if not model or model == "default":
            model = "local-model"
        return client, model

    # 2. Gemini OpenAI-Compatible Endpoint
    if gemini_key:
        client = AsyncOpenAI(
            api_key=gemini_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        if not model or model == "default":
            model = "gemini-2.5-flash"
        elif model.startswith("gemini/"):
            model = model.replace("gemini/", "")
        return client, model

    # 3. Local Ollama Endpoint
    if ollama_base:
        base_url = ollama_base if ollama_base.endswith("/v1") else f"{ollama_base}/v1"
        client = AsyncOpenAI(api_key="ollama", base_url=base_url)
        if not model or model == "default":
            model = "llama3.2"
        return client, model

    # 4. OpenAI or Custom Compatible Endpoint (DeepSeek, Groq, OpenRouter, vLLM)
    if openai_key or custom_base:
        client = AsyncOpenAI(
            api_key=openai_key or "no-key-required",
            base_url=custom_base or "https://api.openai.com/v1",
        )
        if not model or model == "default":
            model = "gpt-4o-mini"
        return client, model

    raise ValueError(
        "No LLM provider configured. Please set GEMINI_API_KEY, OPENAI_API_KEY, LM_STUDIO_API_BASE, or OLLAMA_API_BASE in .env."
    )


async def generate_playwright_code(task: str, metadata: dict[str, Any]) -> str:
    """Generates Playwright Python automation code based on task and page metadata."""
    client, model = get_llm_client()
    logger.info("Generating Playwright code using model '%s' for task: %s", model, task)

    metadata_summary = json.dumps(metadata, indent=2)

    system_prompt = (
        "You are an expert browser automation engineer writing Python code using Playwright.\n"
        "You must generate an async function named `execute(page, context)` that executes the requested task.\n"
        "Guidelines:\n"
        "1. Function signature MUST be: `async def execute(page, context):`\n"
        "2. Use existing selectors and metadata provided. Prefer robust selectors like data-testid, id, name, or role.\n"
        "3. Use `await page.wait_for_selector(selector, state='visible', timeout=7000)` before clicking or typing if needed.\n"
        "4. Return a dictionary or summary string representing the result (e.g. `return {'status': 'success', 'data': ...}`).\n"
        "5. Output ONLY Python code inside ```python ``` blocks. No markdown explanations outside the code block."
    )

    user_prompt = f"""Target Page: {metadata.get('url', 'Unknown')}
Page Title: {metadata.get('title', 'Unknown')}

Page Elements and Metadata:
{metadata_summary}

User Task:
"{task}"

Write the Python async function `async def execute(page, context):` to accomplish this task."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=LLM_TEMPERATURE,
    )

    raw_text = response.choices[0].message.content or ""
    return extract_python_code(raw_text)


async def heal_playwright_code(
    task: str,
    failed_code: str,
    error_trace: str,
    updated_metadata: dict[str, Any],
) -> str:
    """Generates a self-healed, corrected version of the failed Playwright code."""
    client, model = get_llm_client()
    logger.warning("Healing failed Playwright code using model '%s'", model)

    metadata_summary = json.dumps(updated_metadata, indent=2)

    system_prompt = (
        "You are an expert Playwright debugging and self-healing agent.\n"
        "A previously generated Playwright script failed with a runtime exception.\n"
        "Analyze the error traceback and the current page elements, diagnose why it failed, and generate the corrected Python code.\n"
        "Common fixes:\n"
        "- The selector did not match: look at the updated elements list for the right selector or use text-based / role-based locator.\n"
        "- Timeout: wait for element visibility, scroll into view, or use `page.locator(...).first`.\n"
        "- Navigation / Page reload: wait for load state or URL change.\n"
        "Rules:\n"
        "1. Return an async function: `async def execute(page, context):`\n"
        "2. Output ONLY the corrected Python code inside ```python ``` blocks."
    )

    user_prompt = f"""Original User Task:
"{task}"

Failed Python Code:
```python
{failed_code}
```

Runtime Error Traceback:
{error_trace}

Current Page Elements & Metadata:
{metadata_summary}

Please fix the error and output the working `async def execute(page, context):` function."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=LLM_TEMPERATURE,
    )

    raw_text = response.choices[0].message.content or ""
    return extract_python_code(raw_text)
