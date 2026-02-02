"""Human behavior simulation for anti-detection."""
import asyncio
import random
import logging
import time
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


async def random_delay(min_ms: int = 1000, max_ms: int = 3000):
    """Random delay to simulate human behavior."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


async def human_pause(a: float = 1.5, b: float = 4.5):
    """Human-like pause with random delay."""
    await asyncio.sleep(random.uniform(a, b))


async def human_like_scroll(page: Page):
    """Simulate human-like scrolling."""
    actions = [
        lambda: page.mouse.wheel(0, random.randint(200, 600)),
        lambda: page.mouse.wheel(0, random.randint(-300, -100)),
        lambda: page.mouse.wheel(0, random.randint(50, 150)),
    ]
    for _ in range(random.randint(1, 3)):
        await actions[random.randint(0, len(actions) - 1)]()
        await human_pause(0.4, 1.2)


async def human_like_mouse_movement(page: Page):
    """Simulate random mouse movements."""
    x = random.randint(100, 900)
    y = random.randint(100, 700)
    for _ in range(random.randint(2, 6)):
        xr = x + random.randint(-30, 30)
        yr = y + random.randint(-30, 30)
        await page.mouse.move(xr, yr, steps=random.randint(6, 22))
        await human_pause(0.2, 0.6)


async def very_human_behavior(page: Page):
    """Very human-like behavior with mouse movement and scrolling."""
    # Don't bring page to front - it should only be activated for CAPTCHA
    await human_pause()
    await human_like_mouse_movement(page)
    await human_pause(0.5, 2)
    await human_like_scroll(page)
    await human_pause(1, 3)


async def light_human_behavior(page: Page):
    """Light human-like behavior (just scrolling)."""
    # Don't bring page to front - it should only be activated for CAPTCHA
    await human_pause(0.5, 1.5)
    await human_like_scroll(page)
    await human_pause(0.5, 1.2)


async def apply_stealth(page: Page):
    """Apply lightweight stealth patches to reduce automation signals."""
    try:
        await page.add_init_script(
            """
            () => {
              Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
              Object.defineProperty(navigator, 'languages', { get: () => ['ru-RU', 'ru', 'en-US', 'en'] });
              Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
              Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });
              Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
              Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
              const originalQuery = window.navigator.permissions.query;
              window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications'
                  ? Promise.resolve({ state: Notification.permission })
                  : originalQuery(parameters)
              );

              if (window.chrome === undefined) {
                window.chrome = { runtime: {} };
              } else if (!window.chrome.runtime) {
                window.chrome.runtime = {};
              }

              const getParameterProxy = WebGLRenderingContext.prototype.getParameter;
              WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                  return 'NVIDIA Corporation';
                }
                if (parameter === 37446) {
                  return 'NVIDIA GeForce GTX 1650/PCIe/SSE2';
                }
                return getParameterProxy.apply(this, [parameter]);
              };

              const uaData = navigator.userAgentData;
              if (uaData && uaData.getHighEntropyValues) {
                const original = uaData.getHighEntropyValues.bind(uaData);
                uaData.getHighEntropyValues = (hints) =>
                  original(hints).then((values) => ({
                    ...values,
                    platform: 'Windows',
                    platformVersion: '10.0.0',
                    architecture: 'x86',
                    model: ''
                  }));
              }
            }
            """
        )
    except Exception as e:
        logger.warning(f"Stealth init failed: {e}")


async def wait_for_captcha(
    page: Page,
    engine_name: str,
    run_id: Optional[str] = None,
    max_wait_time: int = 180,
    content_check_interval: int = 12,
):
    """Wait for CAPTCHA to be solved, with window management."""
    captcha_detected = False
    start_time = time.time()
    last_content_check = 0.0
    
    # Сначала ждем загрузки страницы
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=10000)
    except:
        pass
    
    while True:
        # Check timeout
        if time.time() - start_time > max_wait_time:
            logger.warning(f"{engine_name}: CAPTCHA wait timeout ({max_wait_time}s)")
            break
        
        try:
            url = page.url.lower()
            # Также проверяем содержимое страницы на наличие CAPTCHA (не на каждом цикле)
            page_content = ""
            if time.time() - last_content_check >= content_check_interval:
                try:
                    page_content = await page.content()
                except:
                    pass
                last_content_check = time.time()
            
            # Check for various CAPTCHA indicators
            is_captcha = (
                "captcha" in url or "showcaptcha" in url or 
                "/sorry" in url or "sorry/index" in url or
                "unusual traffic" in url.lower() or
                "captcha" in page_content.lower() or
                "showcaptcha" in page_content.lower()
            )
            
            if is_captcha:
                if not captcha_detected:
                    # Maximize browser window when captcha is detected
                    logger.warning(f"{engine_name}: CAPTCHA detected! Activating browser window...")
                    try:
                        await page.set_viewport_size({"width": 1920, "height": 1080})
                        await page.bring_to_front()
                        await page.evaluate("() => { window.focus(); }")
                        logger.info(f"{engine_name}: Page brought to front")
                    except Exception as e:
                        logger.error(f"{engine_name}: Error bringing page to front: {e}")
                    
                    # Force window activation via PowerShell (Windows only)
                    try:
                        import os
                        import sys
                        import subprocess
                        if sys.platform == 'win32':
                            # Более надежный способ активации окна Chrome
                            ps_cmd = '''
                            $processes = Get-Process chrome -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -ne ""};
                            if ($processes) {
                                $proc = $processes | Select-Object -First 1;
                                $sig = '[DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h); [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);';
                                $t = Add-Type -MemberDefinition $sig -Name Win32 -Namespace Native -PassThru;
                                $t::ShowWindow($proc.MainWindowHandle, 3); # SW_MAXIMIZE
                                Start-Sleep -Milliseconds 100;
                                $t::SetForegroundWindow($proc.MainWindowHandle);
                            }
                            '''
                            result = subprocess.run(
                                ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_cmd],
                                capture_output=True,
                                timeout=5
                            )
                            if result.returncode == 0:
                                logger.info(f"{engine_name}: Browser window activated via PowerShell")
                            else:
                                logger.warning(f"{engine_name}: Failed to activate window via PowerShell")
                    except Exception as e:
                        logger.error(f"{engine_name}: Error activating window via PowerShell: {e}")
                    
                    captcha_detected = True
                    logger.warning(f"{engine_name}: Капча обнаружена!")
                    logger.warning("=" * 60)
                    logger.warning(f"{engine_name}: КАПЧА ОБНАРУЖЕНА!")
                    logger.warning("=" * 60)
                    
                    # Обновляем статус в backend, если передан run_id
                    if run_id:
                        try:
                            import httpx
                            from ..config import settings
                            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                                await client.put(
                                    f"{settings.BACKEND_URL}/parsing/status/{run_id}",
                                    json={"error_message": "CAPTCHA обнаружена - требуется решение"}
                                )
                            logger.info(f"{engine_name}: Статус CAPTCHA обновлен в backend для run_id: {run_id}")
                        except Exception as e:
                            logger.error(f"{engine_name}: Ошибка обновления статуса CAPTCHA в backend: {e}")
                    
                    # Sound signals - use logger instead of print to avoid encoding issues
                    try:
                        import sys
                        if sys.platform == 'win32':
                            import winsound
                            for _ in range(3):
                                winsound.Beep(1000, 200)
                    except:
                        pass
            
            # Если CAPTCHA не обнаружена, выходим из цикла
            if not is_captcha:
                if captcha_detected:
                    # Restore small window size after captcha is solved
                    try:
                        await page.set_viewport_size({"width": 800, "height": 600})
                    except:
                        pass
                    logger.info(f"[OK] {engine_name}: Капча решена! Продолжаем...")
                break
            
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"{engine_name}: Error checking CAPTCHA: {e}")
            await asyncio.sleep(2)
            continue

