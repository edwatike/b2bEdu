import asyncio
from playwright.async_api import async_playwright

async def test():
    print("Starting Playwright...")
    p = await async_playwright().start()
    print("Launching Chromium...")
    try:
        b = await p.chromium.launch(headless=True)
        print(f"Browser OK: {b.is_connected()}")
        page = await b.new_page()
        await page.goto("https://tophouse.ru", wait_until="domcontentloaded", timeout=15000)
        title = await page.title()
        text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
        print(f"Title: {title}")
        print(f"Text preview: {text[:200]}")
        await page.close()
        await b.close()
    except Exception as e:
        print(f"ERROR: type={type(e).__name__}, msg='{e}'")
    await p.stop()

asyncio.run(test())
