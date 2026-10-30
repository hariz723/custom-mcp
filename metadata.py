import logging
from typing import Any

from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def extract_page_metadata(page: Page) -> dict[str, Any]:
    """Extracts structural metadata, meta tags, and interactive elements from the active page."""
    logger.info("Extracting page metadata from: %s", page.url)

    metadata_js = """
    () => {
        // Helper: get unique CSS selector
        function getCssSelector(el) {
            if (el.id) return '#' + CSS.escape(el.id);
            if (el.getAttribute('data-testid')) return `[data-testid="${CSS.escape(el.getAttribute('data-testid'))}"]`;
            if (el.getAttribute('name')) return `[name="${CSS.escape(el.getAttribute('name'))}"]`;
            if (el.getAttribute('aria-label')) return `[aria-label="${CSS.escape(el.getAttribute('aria-label'))}"]`;

            let path = [];
            while (el && el.nodeType === Node.ELEMENT_NODE) {
                let selector = el.nodeName.toLowerCase();
                if (el.id) {
                    path.unshift('#' + CSS.escape(el.id));
                    break;
                }
                let sibling = el;
                let nth = 1;
                while (sibling = sibling.previousElementSibling) {
                    if (sibling.nodeName.toLowerCase() === selector) nth++;
                }
                if (nth > 1) selector += `:nth-of-type(${nth})`;
                path.unshift(selector);
                el = el.parentNode;
                if (path.length >= 3) break;
            }
            return path.join(' > ');
        }

        // 1. Meta tags
        const metaTags = {};
        document.querySelectorAll('meta').forEach(meta => {
            const name = meta.getAttribute('name') || meta.getAttribute('property');
            const content = meta.getAttribute('content');
            if (name && content) {
                metaTags[name] = content;
            }
        });

        // 2. Canonical URL
        const canonical = document.querySelector('link[rel="canonical"]')?.href || null;

        // 3. Headings structure
        const headings = [];
        document.querySelectorAll('h1, h2, h3').forEach(h => {
            const text = h.innerText?.trim();
            if (text) {
                headings.push({ tag: h.tagName.toLowerCase(), text: text });
            }
        });

        // 4. Interactive Inputs & Forms
        const inputs = [];
        document.querySelectorAll('input, textarea, select').forEach((el, index) => {
            if (index > 40) return; // Limit to prevent overwhelming prompt
            const type = el.getAttribute('type') || (el.tagName.toLowerCase() === 'textarea' ? 'textarea' : 'text');
            if (type === 'hidden') return;

            let labelText = '';
            if (el.id) {
                const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
                if (label) labelText = label.innerText?.trim();
            }
            if (!labelText && el.closest('label')) {
                labelText = el.closest('label').innerText?.trim();
            }

            inputs.push({
                tag: el.tagName.toLowerCase(),
                type: type,
                id: el.id || null,
                name: el.name || null,
                placeholder: el.placeholder || null,
                label: labelText || null,
                selector: getCssSelector(el)
            });
        });

        // 5. Buttons & Action Elements
        const buttons = [];
        document.querySelectorAll('button, input[type="submit"], input[type="button"], [role="button"], a.btn').forEach((btn, index) => {
            if (index > 30) return;
            const text = (btn.innerText || btn.value || btn.getAttribute('aria-label') || '').trim();
            if (text) {
                buttons.push({
                    text: text.slice(0, 50),
                    id: btn.id || null,
                    selector: getCssSelector(btn),
                    type: btn.getAttribute('type') || 'button'
                });
            }
        });

        // 6. Primary Links (Top navigation / important anchors)
        const links = [];
        document.querySelectorAll('nav a, header a, main a').forEach((a, index) => {
            if (index > 25) return;
            const text = a.innerText?.trim();
            if (text && a.href && !a.href.startsWith('javascript:')) {
                links.push({
                    text: text.slice(0, 40),
                    href: a.href,
                    selector: getCssSelector(a)
                });
            }
        });

        return {
            title: document.title || '',
            url: window.location.href,
            meta: metaTags,
            canonical: canonical,
            headings: headings.slice(0, 15),
            inputs: inputs,
            buttons: buttons,
            links: links
        };
    }
    """

    try:
        data = await page.evaluate(metadata_js)
        return data
    except Exception as e:
        logger.error("Failed to extract metadata via evaluate: %s", e)
        # Fallback basic metadata
        return {
            "title": await page.title(),
            "url": page.url,
            "meta": {},
            "headings": [],
            "inputs": [],
            "buttons": [],
            "links": [],
            "error": str(e)
        }
