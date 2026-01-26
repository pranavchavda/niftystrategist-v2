import { chromium } from 'playwright';

(async () => {
  const browser = await chromium.launch({ headless: false });
  const context = await browser.newContext();
  const page = await context.newPage();

  console.log('📱 Loading http://localhost:5173...');
  await page.goto('http://localhost:5173');

  // Click dev mode to bypass login
  console.log('🔓 Clicking dev mode...');
  await page.click('text="Continue without authentication (Dev Mode)"');

  // Wait for chat interface to load
  await page.waitForTimeout(2000);

  // Take screenshot of the main interface
  await page.screenshot({ path: 'catalyst_ui.png', fullPage: true });
  console.log('📸 Screenshot saved as catalyst_ui.png');

  // Check if sidebar exists and get its computed styles
  const sidebarStyles = await page.evaluate(() => {
    const sidebar = document.querySelector('[data-slot="sidebar"]') ||
                   document.querySelector('aside') ||
                   document.querySelector('.sidebar');
    if (!sidebar) return null;

    const styles = window.getComputedStyle(sidebar);
    return {
      backgroundColor: styles.backgroundColor,
      width: styles.width,
      borderRight: styles.borderRight,
      display: styles.display,
      position: styles.position,
      height: styles.height
    };
  });

  console.log('🎨 Sidebar styles:', sidebarStyles);

  // Get body styles to see zinc colors
  const bodyStyles = await page.evaluate(() => {
    const styles = window.getComputedStyle(document.body);
    return {
      backgroundColor: styles.backgroundColor,
      fontFamily: styles.fontFamily,
      color: styles.color
    };
  });

  console.log('🎨 Body styles:', bodyStyles);

  // Check for Tailwind classes
  const tailwindClasses = await page.evaluate(() => {
    const elements = document.querySelectorAll('[class*="zinc"], [class*="bg-"], [class*="text-"]');
    const classes = new Set();
    elements.forEach(el => {
      el.className.split(' ').forEach(cls => {
        if (cls.includes('zinc') || cls.includes('bg-') || cls.includes('text-')) {
          classes.add(cls);
        }
      });
    });
    return Array.from(classes).slice(0, 20);
  });

  console.log('🎨 Sample Tailwind classes found:', tailwindClasses);

  await browser.close();
})();