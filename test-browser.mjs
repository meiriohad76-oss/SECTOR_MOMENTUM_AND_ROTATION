import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

// Capture console
const logs = [];
page.on('console', m => logs.push(`${m.type()}: ${m.text()}`));
page.on('pageerror', e => logs.push(`PAGEERROR: ${e.message}`));

// Capture relevant network
const reqs = [];
page.on('request', req => {
  const u = req.url();
  if (u.includes('refresh') || u.includes('_next/action') || u.includes('api/v1')) {
    reqs.push(`→ ${req.method()} ${u}`);
  }
});
page.on('response', async resp => {
  const u = resp.url();
  if (u.includes('refresh') || u.includes('_next/action') || u.includes('api/v1')) {
    reqs.push(`← ${resp.status()} ${u}`);
  }
});

console.log('=== Loading page ===');
await page.goto('http://localhost:3100/', { waitUntil: 'networkidle', timeout: 30000 });
console.log('Title:', await page.title());

// Find refresh buttons
const buttons = await page.locator('[class*="refresh-btn"]').all();
console.log(`\n=== Found ${buttons.length} refresh-btn elements ===`);
for (let i = 0; i < buttons.length; i++) {
  const text = await buttons[i].textContent();
  const cls = await buttons[i].getAttribute('class');
  const disabled = await buttons[i].isDisabled();
  const visible = await buttons[i].isVisible();
  console.log(`Button[${i}]: visible=${visible} disabled=${disabled} text=${JSON.stringify(text?.trim())} class=${cls}`);
}

if (buttons.length > 0) {
  console.log('\n=== Clicking first refresh button ===');
  await buttons[0].click();

  // Wait briefly to see if anything changes
  await page.waitForTimeout(3000);

  const newText = await buttons[0].textContent().catch(() => 'GONE');
  const newCls = await buttons[0].getAttribute('class').catch(() => 'GONE');
  console.log(`After click: text=${JSON.stringify(newText?.trim())} class=${newCls}`);
}

console.log('\n=== Console messages ===');
logs.forEach(l => console.log(' ', l));

console.log('\n=== Network (refresh/action) ===');
reqs.forEach(r => console.log(' ', r));

await browser.close();
