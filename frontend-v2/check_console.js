import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  // Listen to console messages
  page.on('console', msg => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error') {
      console.log('❌ Console Error:', text);
    } else if (type === 'warning') {
      console.log('⚠️ Console Warning:', text);
    } else {
      console.log(`📝 Console ${type}:`, text);
    }
  });

  // Listen to page errors
  page.on('pageerror', error => {
    console.log('❌ Page Error:', error.message);
  });

  // Listen to request failures
  page.on('requestfailed', request => {
    console.log('❌ Request Failed:', request.url(), request.failure()?.errorText);
  });

  console.log('📱 Loading http://localhost:5173...');
  await page.goto('http://localhost:5173', { waitUntil: 'networkidle' });

  // Check if root element exists and has content
  const rootContent = await page.evaluate(() => {
    const root = document.getElementById('root');
    if (!root) return 'No root element found';
    return {
      hasChildren: root.children.length > 0,
      innerHTML: root.innerHTML.substring(0, 200),
      childCount: root.children.length
    };
  });

  console.log('🔍 Root element status:', rootContent);

  // Get computed styles on body
  const bodyStyles = await page.evaluate(() => {
    const styles = window.getComputedStyle(document.body);
    return {
      backgroundColor: styles.backgroundColor,
      color: styles.color,
      fontFamily: styles.fontFamily
    };
  });

  console.log('🎨 Body styles:', bodyStyles);

  // Take a screenshot
  await page.screenshot({ path: 'debug_screenshot.png' });
  console.log('📸 Screenshot saved as debug_screenshot.png');

  // Keep browser open for 5 seconds to see any delayed errors
  await page.waitForTimeout(5000);

  await browser.close();
})();