import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Literal, Optional

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from browser import browser_manager, clean_html_content
from config import (
    HOST,
    MAX_RETRIES,
    PDFS_DIR,
    PORT,
    SCREENSHOTS_DIR,
    SERVER_NAME,
    TRANSPORT,
)
from executor import execute_with_self_healing
from metadata import extract_page_metadata

# Logging configuration: stdout must stay clean for stdio transport
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("playwright-mcp-server")

# Initialize MCP Server
mcp = MCPServer(SERVER_NAME)


# ============================================================================
# Flagship Autonomous & Self-Healing Tools
# ============================================================================

@mcp.tool()
async def browser_auto_task(
    task_instruction: str,
    url: Optional[str] = None,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Autonomously inspects a page, generates automation code, executes it, and heals any runtime errors using LLM.

    Args:
        task_instruction: High-level goal (e.g. 'search for laptops, click the first result, and return its title and price').
        url: Optional URL to navigate to first. If omitted, uses current active page.
        max_retries: Maximum number of self-healing attempts if errors occur during execution.
    """
    page = await browser_manager.get_page()
    context = page.context

    if url:
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        logger.info("Auto-task navigating to: %s", url)
        await page.goto(url, wait_until="domcontentloaded")

    result = await execute_with_self_healing(
        task=task_instruction,
        page=page,
        context=context,
        initial_code=None,
        max_retries=max_retries,
    )

    return json.dumps(result, indent=2)


@mcp.tool()
async def browser_scrape_metadata(url: Optional[str] = None) -> str:
    """Scrapes comprehensive metadata from the page including title, meta tags, forms, buttons, inputs, and selectors.

    Args:
        url: Optional URL to visit before extracting metadata. If omitted, extracts from current page.
    """
    page = await browser_manager.get_page()

    if url:
        if not url.startswith(("http://", "https://", "file://")):
            url = "https://" + url
        await page.goto(url, wait_until="domcontentloaded")

    data = await extract_page_metadata(page)
    return json.dumps(data, indent=2)


@mcp.tool()
async def browser_execute_script(
    python_code: str,
    task_description: Optional[str] = None,
    auto_heal: bool = True,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Executes a custom Playwright Python snippet on the live page, optionally self-healing if it fails.

    Args:
        python_code: Python code defining `async def execute(page, context):`.
        task_description: Description of what this code is trying to do (used by LLM if self-healing is triggered).
        auto_heal: If True, invokes the LLM to fix the script if any runtime exception occurs.
        max_retries: Number of heal attempts before giving up.
    """
    page = await browser_manager.get_page()
    context = page.context

    if auto_heal:
        task = task_description or "Execute the provided Playwright script successfully."
        result = await execute_with_self_healing(
            task=task,
            page=page,
            context=context,
            initial_code=python_code,
            max_retries=max_retries,
        )
        return json.dumps(result, indent=2)
    else:
        from executor import run_dynamic_code
        try:
            res = await run_dynamic_code(python_code, page, context)
            return json.dumps({"success": True, "result": res}, indent=2)
        except Exception as e:
            import traceback
            return json.dumps({"success": False, "error": str(e), "traceback": traceback.format_exc()}, indent=2)


# ============================================================================
# Granular Primitives for Manual Browser Control
# ============================================================================

@mcp.tool()
async def browser_navigate(
    url: str,
    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = "load",
) -> str:
    """Navigate the browser to a URL.

    Args:
        url: The address to visit. If scheme is omitted, https:// is prepended.
        wait_until: Wait condition: 'load', 'domcontentloaded', 'networkidle', or 'commit'.
    """
    if not url.startswith(("http://", "https://", "file://")):
        url = "https://" + url

    page = await browser_manager.get_page()
    logger.info("Navigating to %s (wait_until=%s)", url, wait_until)
    response = await page.goto(url, wait_until=wait_until)

    status_code = response.status if response else "unknown"
    title = await page.title()
    return (
        f"Navigated to: {page.url}\n"
        f"Title: {title}\n"
        f"HTTP Status: {status_code}"
    )


@mcp.tool()
async def browser_screenshot(
    name: Optional[str] = None,
    full_page: bool = False,
    selector: Optional[str] = None,
) -> str:
    """Capture a screenshot of the current page or a specific element and save it to disk.

    Args:
        name: Filename for the screenshot. Defaults to timestamped name.
        full_page: When True, captures the full scrolling page.
        selector: Optional CSS or XPath selector to screenshot just that element.
    """
    page = await browser_manager.get_page()

    if not name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"screenshot_{timestamp}.png"
    elif not name.endswith(".png"):
        name = f"{name}.png"

    file_path = SCREENSHOTS_DIR / name

    if selector:
        element = await page.wait_for_selector(selector, state="visible")
        if not element:
            return f"Error: Element matching '{selector}' not found."
        await element.screenshot(path=str(file_path))
        return f"Element screenshot saved to: {file_path}"
    else:
        await page.screenshot(path=str(file_path), full_page=full_page)
        return f"Page screenshot (full_page={full_page}) saved to: {file_path}"


@mcp.tool()
async def browser_click(selector: str, timeout_ms: int = 5000) -> str:
    """Click an element on the active page.

    Args:
        selector: CSS or XPath selector of the element to click.
        timeout_ms: Maximum time to wait for the element to be clickable (ms).
    """
    page = await browser_manager.get_page()
    await page.click(selector, timeout=timeout_ms)
    return f"Successfully clicked: {selector}"


@mcp.tool()
async def browser_fill(selector: str, value: str, timeout_ms: int = 5000) -> str:
    """Fill an input field or form control with text.

    Args:
        selector: CSS or XPath selector of the target input element.
        value: Text value to enter.
        timeout_ms: Maximum time to wait for the element (ms).
    """
    page = await browser_manager.get_page()
    await page.fill(selector, value, timeout=timeout_ms)
    return f"Successfully filled '{selector}' with: {value}"


@mcp.tool()
async def browser_press_key(key: str) -> str:
    """Press a keyboard key on the active page.

    Args:
        key: Key name such as 'Enter', 'Tab', 'Escape', 'ArrowDown'.
    """
    page = await browser_manager.get_page()
    await page.keyboard.press(key)
    return f"Pressed keyboard key: {key}"


@mcp.tool()
async def browser_get_text(selector: str = "body") -> str:
    """Extract visible plain text from the page or a specific container.

    Args:
        selector: CSS or XPath selector. Defaults to 'body' for full page text.
    """
    page = await browser_manager.get_page()
    element = await page.wait_for_selector(selector)
    if not element:
        return f"Error: Element matching '{selector}' not found."

    text = await element.inner_text()
    cleaned_lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(cleaned_lines)


@mcp.tool()
async def browser_get_html(selector: Optional[str] = None, clean: bool = True) -> str:
    """Extract HTML content from the current page.

    Args:
        selector: Optional selector to limit HTML retrieval to a specific element.
        clean: When True (recommended), strips script, style, and svg tags to save tokens.
    """
    page = await browser_manager.get_page()

    if selector:
        element = await page.wait_for_selector(selector)
        if not element:
            return f"Error: Element matching '{selector}' not found."
        raw_html = await element.inner_html()
    else:
        raw_html = await page.content()

    if clean:
        return clean_html_content(raw_html)
    return raw_html


@mcp.tool()
async def browser_evaluate(script: str) -> str:
    """Execute a custom JavaScript expression in the page context and return the result.

    Args:
        script: JavaScript code/expression to evaluate (e.g. 'document.title').
    """
    page = await browser_manager.get_page()
    result = await page.evaluate(script)
    try:
        return json.dumps(result, indent=2)
    except Exception:
        return str(result)


@mcp.tool()
async def browser_pdf(name: Optional[str] = None) -> str:
    """Generate a PDF of the current page and save it to disk.

    Args:
        name: Filename for the PDF (e.g. 'report.pdf'). Defaults to timestamped name.
    """
    page = await browser_manager.get_page()

    if not name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"page_{timestamp}.pdf"
    elif not name.endswith(".pdf"):
        name = f"{name}.pdf"

    file_path = PDFS_DIR / name
    await page.pdf(path=str(file_path), print_background=True)
    return f"PDF saved successfully to: {file_path}"


@mcp.tool()
async def browser_reset() -> str:
    """Reset the current page and context, clearing cookies, cache, and active tabs."""
    await browser_manager.reset()
    return "Browser session reset successfully. Next command will launch a clean page."


@mcp.tool()
async def browser_close() -> str:
    """Close the browser completely and terminate browser background processes."""
    await browser_manager.close()
    return "Browser closed successfully."


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous Playwright MCP Server")
    parser.add_argument(
        "--transport",
        default=TRANSPORT,
        choices=["streamable-http", "stdio", "sse"],
        help="Transport to use for MCP communication",
    )
    parser.add_argument("--host", default=HOST, help="Host to bind for HTTP/SSE")
    parser.add_argument("--port", type=int, default=PORT, help="Port to bind for HTTP/SSE")
    args = parser.parse_args()

    security = TransportSecuritySettings(enable_dns_rebinding_protection=False)

    if args.transport == "streamable-http":
        logger.info(
            "Starting Autonomous Playwright MCP server with Streamable HTTP on %s:%s/mcp",
            args.host,
            args.port,
        )
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            transport_security=security,
        )
    elif args.transport == "sse":
        logger.info(
            "Starting Autonomous Playwright MCP server with SSE on %s:%s/sse",
            args.host,
            args.port,
        )
        mcp.run(
            transport="sse",
            host=args.host,
            port=args.port,
            transport_security=security,
        )
    else:
        logger.info("Starting Autonomous Playwright MCP server over stdio")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
