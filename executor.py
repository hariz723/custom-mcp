import asyncio
import inspect
import logging
import traceback
from typing import Any

from playwright.async_api import BrowserContext, Page

from config import MAX_RETRIES
from llm import generate_playwright_code, heal_playwright_code
from metadata import extract_page_metadata

logger = logging.getLogger(__name__)


async def run_dynamic_code(code_str: str, page: Page, context: BrowserContext) -> Any:
    """Safely executes an async Playwright Python code block against the live page."""
    # Local scope with necessary modules and objects
    local_scope: dict[str, Any] = {
        "page": page,
        "context": context,
        "asyncio": asyncio,
        "result": None,
    }

    # Compile the code
    compiled = compile(code_str, "<dynamic_playwright_script>", "exec")
    exec(compiled, local_scope)

    # The code is expected to define `execute(page, context)`
    execute_func = local_scope.get("execute")
    if not execute_func or not callable(execute_func):
        raise ValueError(
            "The code must define an async function: `async def execute(page, context):`"
        )

    if inspect.iscoroutinefunction(execute_func):
        return await execute_func(page, context)
    else:
        return execute_func(page, context)


async def execute_with_self_healing(
    task: str,
    page: Page,
    context: BrowserContext,
    initial_code: str | None = None,
    max_retries: int = MAX_RETRIES,
) -> dict[str, Any]:
    """Executes code on the live page with automatic metadata-driven LLM self-healing."""
    history = []

    # 1. Scrape metadata
    metadata = await extract_page_metadata(page)

    # 2. Generate initial code if not provided
    if initial_code:
        current_code = initial_code
    else:
        current_code = await generate_playwright_code(task, metadata)

    # 3. Execution & Self-Healing Loop
    for attempt in range(1, max_retries + 1):
        logger.info("Executing task attempt %d/%d", attempt, max_retries)
        try:
            result = await run_dynamic_code(current_code, page, context)
            logger.info("Task completed successfully on attempt %d", attempt)
            return {
                "success": True,
                "attempts_used": attempt,
                "result": result if result is not None else "Execution completed with no return value.",
                "final_code": current_code,
                "self_healed": attempt > 1,
                "healing_history": history,
            }
        except Exception as e:
            error_trace = traceback.format_exc()
            logger.warning("Attempt %d failed with error: %s", attempt, str(e))

            history.append({
                "attempt": attempt,
                "failed_code": current_code,
                "error_message": str(e),
                "traceback": error_trace,
            })

            if attempt == max_retries:
                logger.error("Exhausted all %d attempts for task.", max_retries)
                break

            # 4. Self-Healing: Inspect current DOM and invoke LLM to heal the code
            logger.info("Attempting automatic self-healing for attempt %d...", attempt + 1)
            updated_metadata = await extract_page_metadata(page)
            current_code = await heal_playwright_code(
                task=task,
                failed_code=current_code,
                error_trace=error_trace,
                updated_metadata=updated_metadata,
            )

    return {
        "success": False,
        "attempts_used": max_retries,
        "error": f"Task failed after {max_retries} attempts.",
        "last_code": current_code,
        "self_healed": False,
        "healing_history": history,
    }
