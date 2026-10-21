import { expect, test, type Page } from '@playwright/test';
import type { Report, Workspace } from '../src/types';

const report = (id: number, owner: number, status: Report['status']): Report => ({
  id, owner_id: owner, owner_name: owner === 7 ? 'Sinov Xodimi' : 'Hamkasb Xodimi',
  title: `Hisobot ${id}`, type: 'scientific', period: '2026-yil', status,
  activity_ids: [], comment: '', due_date: null, submitted_at: null,
  created_at: '2026-10-01', updated_at: '2026-10-01', history: [],
});
const workspace: Workspace = {
  user: { id: 7, name: 'Sinov Xodimi', email: 'test@example.com', role: 'reviewer', initials: 'SX' },
  profile: { id: 7, full_name: 'Sinov Xodimi', email: 'test@example.com', phone: '', department: 'Sinov kafedrasi', faculty: 'Sinov fakulteti', position: 'O‘qituvchi', degree: '', bio: '', employee_id: 'TEST-7', initials: 'SX', experience_years: 2, employment_type: 'full_time' },
  activities: [7, 8].map(owner => ({ id: owner, owner_id: owner, owner_name: 'Sinov Xodimi', title: owner === 7 ? 'Shaxsiy ilmiy maqola' : 'Hamkasbning maqolasi', category: 'article', date: '2026-10-01', description: '', link: '', status: 'draft', attachment: null, created_at: '2026-10-01' })),
  reports: [report(1, 7, 'returned'), report(2, 8, 'returned'), report(3, 7, 'submitted'), report(4, 8, 'submitted')],
  work_items: [], notifications: [], templates: [],
};
async function ready(page: Page) {
  await page.route('**/api/auth/session/', route => route.fulfill({ json: { user: workspace.user } }));
  await page.route('**/api/workspace/', route => route.fulfill({ json: workspace }));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Xayrli kun/ })).toBeVisible();
}

test('closed mobile navigation is skipped by keyboard; open navigation traps focus and restores it', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  const opener = page.getByRole('button', { name: 'Menyuni ochish' });
  await expect(opener).toHaveAttribute('aria-expanded', 'false');
  await page.keyboard.press('Tab');
  await expect(opener).toBeFocused();
  await page.keyboard.press('Enter');
  const menu = page.getByRole('dialog', { name: 'Asosiy menyu' });
  const closer = menu.getByRole('button', { name: 'Menyuni yopish' });
  await expect(closer).toBeFocused();
  await expect(page.locator('.main-layout')).toHaveAttribute('inert', '');
  await page.keyboard.press('Shift+Tab');
  await expect(menu.locator('.sidebar-user')).toBeFocused();
  await page.keyboard.press('Tab');
  await expect(closer).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(menu).toHaveCount(0);
  await expect(opener).toBeFocused();
  await expect(page.locator('.sidebar')).toHaveAttribute('inert', '');
  await expect(page.locator('.main-layout')).not.toHaveAttribute('inert', '');

  await opener.click();
  await page.getByRole('dialog', { name: 'Asosiy menyu' }).getByRole('button', { name: 'Hisobotlarim' }).click();
  await expect(page.getByRole('heading', { name: 'Hisobotlarim', exact: true })).toBeVisible();
  await expect(opener).toBeFocused();
  await expect(page.locator('.sidebar')).toHaveAttribute('inert', '');

  await opener.click();
  await page.getByRole('dialog', { name: 'Asosiy menyu' }).getByRole('button', { name: 'Qo‘llanmani ko‘rish' }).click();
  const help = page.getByRole('dialog', { name: 'UniFlow bilan ishlash' });
  await expect(help).toBeFocused();
  await expect(page.locator('body')).toHaveCSS('overflow', 'hidden');
  await page.keyboard.press('Escape');
  await expect(help).toHaveCount(0);
  await expect(opener).toBeFocused();

  await page.setViewportSize({ width: 1440, height: 1000 });
  await expect(page.locator('.sidebar')).not.toHaveAttribute('inert', '');
  await page.getByRole('navigation', { name: 'Asosiy navigatsiya' }).getByRole('button', { name: 'Ish stolim' }).click();
  await expect(page.getByRole('heading', { name: /Xayrli kun/ })).toBeVisible();
});

for (const width of [390, 1440]) {
  test(`helper text meets 4.5:1 contrast at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await ready(page);
    const contrasts = await page.evaluate(() => {
      const selectors = ['.page-heading p', '.eyebrow', '.stat-top', '.stat-detail', '.stat-detail .positive', '.stat-detail .attention', '.section-heading p', '.chart-legend', '.chart-footnote', '.chart-column .current-month', '.welcome-banner p', '.quick-action b'];
      if (window.innerWidth > 800) selectors.push('.nav-item', '.sidebar-help button');
      function rgb(value: string) { return value.match(/[\d.]+/g)!.map(Number).slice(0, 3); }
      function luminance(color: number[]) {
        const linear = color.map(channel => { const value = channel / 255; return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4; });
        return linear[0] * .2126 + linear[1] * .7152 + linear[2] * .0722;
      }
      return selectors.flatMap(selector => [...document.querySelectorAll<HTMLElement>(selector)].map(element => {
        let ancestor: HTMLElement | null = element;
        let background = 'rgb(255, 255, 255)';
        while (ancestor) {
          const candidate = getComputedStyle(ancestor).backgroundColor;
          if (candidate !== 'rgba(0, 0, 0, 0)' && candidate !== 'transparent') { background = candidate; break; }
          ancestor = ancestor.parentElement;
        }
        const foreground = luminance(rgb(getComputedStyle(element).color));
        const back = luminance(rgb(background));
        return { selector, contrast: (Math.max(foreground, back) + .05) / (Math.min(foreground, back) + .05) };
      }));
    });
    expect(contrasts.length).toBeGreaterThan(10);
    for (const value of contrasts) expect(value.contrast, value.selector).toBeGreaterThanOrEqual(4.5);
  });
}

test('navigation counts and activity search reflect actionable personal and review records', async ({ page }) => {
  await ready(page);
  const navigation = page.getByRole('navigation', { name: 'Asosiy navigatsiya' });
  await expect(navigation.getByRole('button', { name: 'Hisobotlarim' }).locator('.nav-count')).toHaveText('1');
  await expect(navigation.getByRole('button', { name: 'Tekshiruv markazi' }).locator('.nav-count')).toHaveText('1');
  await page.getByLabel('Platformada qidirish').fill('Hamkasbning maqolasi');
  await expect(page.locator('.search-results')).toContainText('Hech narsa topilmadi.');
  await page.getByLabel('Platformada qidirish').fill('Shaxsiy ilmiy maqola');
  await expect(page.locator('.search-results').getByRole('button', { name: /Shaxsiy ilmiy maqola/ })).toBeVisible();
});
