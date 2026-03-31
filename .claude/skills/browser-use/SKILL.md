---
name: browser-use
description: Automate browser interactions for testing, scraping, form filling, and UI verification. Use this skill when the user needs to interact with a web page, test a UI, check a website, fill forms, take screenshots, or verify web application behavior. Trigger on mentions of browser, webpage, URL testing, UI testing, or web scraping.
---

# Browser Use

Control a browser to interact with web pages, test UIs, and verify web behavior.

## Capabilities

- Navigate to URLs and interact with page elements
- Fill forms, click buttons, scroll pages
- Take screenshots for visual verification
- Read page content and accessibility trees
- Monitor network requests and console logs
- Test responsive layouts at different viewport sizes

## Process

1. Get tab context with `tabs_context_mcp` first
2. Create a new tab or use an existing one
3. Navigate, interact, and observe
4. Report findings with screenshots when useful

## Guidelines

- Always get tab context before any browser operation
- Use `read_page` or `find` to locate elements before clicking
- Take screenshots to verify visual state
- Use `get_page_text` for content extraction
- Monitor console for JavaScript errors when debugging
- Respect privacy: don't enter sensitive data, don't bypass CAPTCHAs
