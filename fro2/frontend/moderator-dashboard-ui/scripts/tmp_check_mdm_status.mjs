import { chromium } from '@playwright/test';
(async()=>{
 const browser=await chromium.connectOverCDP('http://127.0.0.1:7000');
 const context=browser.contexts()[0]??await browser.newContext();
 const page=await context.newPage();
 await page.goto('http://localhost:3000/parsing-runs/37a83af3-e063-499a-a2d1-fc82ea52226c',{waitUntil:'domcontentloaded',timeout:120000});
 await page.waitForTimeout(5000);
 const row=page.locator('table tbody tr',{hasText:'mdm-complect.ru'}).first();
 const txt=await row.innerText();
 console.log(txt.replace(/\s+/g,' ').trim());
 await page.close(); await browser.close();
})();
