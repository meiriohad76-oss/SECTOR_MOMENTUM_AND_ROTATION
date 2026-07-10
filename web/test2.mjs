import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const logs = [];
page.on('console', m => logs.push(m.type() + ': ' + m.text()));
page.on('pageerror', e => logs.push('PAGEERROR: ' + e.message));

const net = [];
page.on('request', req => {
  const m = req.method(), u = req.url(), h = req.headers();
  if (m === 'POST' || h['next-action']) net.push('REQ ' + m + ' ' + u + (h['next-action'] ? ' [Act:' + h['next-action'].slice(0,8)+']' : ''));
});
page.on('response', async r => {
  const u = r.url(), m = r.request().method();
  if (m === 'POST' || r.request().headers()['next-action']) {
    let b = ''; try { b = (await r.text()).slice(0,400); } catch {}
    net.push('RES ' + r.status() + ' ' + u + ' BODY:' + b);
  }
});

await page.goto('http://localhost:3100/', { waitUntil: 'load', timeout: 30000 });
await page.waitForTimeout(3000); // wait for hydration

const all = await page.locator('[class*="refresh"]').all();
console.log('All refresh elements:', all.length);
for (const el of all) {
  const tag = await el.evaluate(e => e.tagName);
  const cls = await el.getAttribute('class');
  const txt = await el.textContent();
  console.log(' ', tag, '|', cls, '| text:', JSON.stringify(txt?.trim()));
}

// Also check toolbar area
const toolbar = await page.locator('[class*="display-toolbar"], [class*="toolbar"]').all();
console.log('Toolbar elements:', toolbar.length);

// Check for any buttons with aria-label containing Refresh
const refreshBtns = await page.locator('button[aria-label*="Refresh"], button[title*="Refresh"]').all();
console.log('Buttons with Refresh label:', refreshBtns.length);
for (const btn of refreshBtns) {
  console.log(' label:', await btn.getAttribute('aria-label'), 'disabled:', await btn.isDisabled());
}

if (refreshBtns.length > 0) {
  net.length = 0; logs.length = 0;
  console.log('\nClicking first Refresh button...');
  await refreshBtns[0].click();
  await page.waitForTimeout(5000);
  const cls2 = await refreshBtns[0].getAttribute('class').catch(() => 'GONE');
  console.log('Button class after 5s:', cls2);
}

console.log('\n--- Console ---');
logs.forEach(l => console.log(l));
console.log('\n--- Network POST ---');
if (net.length === 0) console.log('NONE');
net.forEach(r => console.log(r));

await browser.close();
