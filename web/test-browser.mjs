import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

const logs = [];
page.on('console', m => logs.push(m.type() + ': ' + m.text()));
page.on('pageerror', e => logs.push('PAGEERROR: ' + e.message));

const allReqs = [];
page.on('request', req => {
  const method = req.method();
  const url = req.url();
  const hdrs = req.headers();
  if (method === 'POST' || url.includes('action') || url.includes('refresh') || url.includes('_next')) {
    allReqs.push('REQ ' + method + ' ' + url.slice(0, 100) + (hdrs['next-action'] ? ' [NextAction=' + hdrs['next-action'].slice(0,8) + ']' : ''));
  }
});
page.on('response', async resp => {
  const url = resp.url();
  const method = resp.request().method();
  if (method === 'POST' || url.includes('action') || url.includes('refresh')) {
    let body = '';
    try { body = (await resp.text()).slice(0, 300); } catch {}
    allReqs.push('RES ' + resp.status() + ' ' + url.slice(0, 100) + ' | ' + body);
  }
});

await page.goto('http://localhost:3100/', { waitUntil: 'networkidle', timeout: 30000 });
console.log('Title:', await page.title());

const buttons = await page.locator('[class*="refresh-btn--idle"]').all();
console.log('Idle refresh buttons found:', buttons.length);

if (buttons.length > 0) {
  allReqs.length = 0;
  logs.length = 0;
  console.log('Clicking button[0]...');
  await buttons[0].click();
  await page.waitForTimeout(5000);
  const cls = await buttons[0].getAttribute('class').catch(() => 'GONE');
  console.log('Button class after 5s:', cls);
}

console.log('--- Console ---');
logs.forEach(l => console.log(l));
console.log('--- Network (POST/action/refresh) ---');
if (allReqs.length === 0) console.log('NONE - no network requests made by click');
allReqs.forEach(r => console.log(r));
await browser.close();
