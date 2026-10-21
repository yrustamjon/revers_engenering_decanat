import { test, expect, type Page } from '@playwright/test';
import type { Activity, Report, Role, Workspace } from '../src/types';

const timestamp = '2026-10-20T09:00:00Z';
function activity(id: number, owner: number, title: string): Activity {
  return { id, owner_id: owner, owner_name: 'Bir xil ism', title, category: 'article', date: '2026-10-20', description: '', link: '', attachment: null, status: 'draft', created_at: timestamp };
}
function report(id: number, owner: number, title: string, status: Report['status']): Report {
  return { id, owner_id: owner, owner_name: 'Bir xil ism', title, type: 'scientific', period: '2026-yil', status, activity_ids: [], comment: '', due_date: null, submitted_at: null, created_at: timestamp, updated_at: timestamp, history: [] };
}
function workspace(role: Role): Workspace {
  return {
    user: { id: 1, name: 'Bir xil ism', email: 'scope@example.com', role, initials: 'BI' },
    profile: { id: 1, full_name: 'Bir xil ism', email: 'scope@example.com', phone: '', department: 'Test bo‘limi', faculty: '', position: 'O‘qituvchi', degree: '', bio: '', employee_id: 'SCOPE-1', initials: 'BI', experience_years: 1, employment_type: 'full_time' },
    activities: [activity(1, 1, 'O‘zimning maqolam'), activity(2, 2, 'Hamkasbning maqolasi')],
    reports: [report(1, 1, 'O‘zimning qoralamam', 'draft'), report(2, 1, 'O‘zimning tasdiqlangan hisobotim', 'approved'), report(3, 2, 'Hamkasbning qoralamasi', 'draft'), report(4, 2, 'Hamkasbning tekshiruvdagi hisoboti', 'submitted'), report(5, 2, 'Hamkasbning arxivdagi hisoboti', 'approved')],
    work_items: [], notifications: [], templates: [],
  };
}
async function navigate(page: Page, name: string) {
  await page.locator('.sidebar-navigation').getByRole('button', { name: new RegExp(`^${name}(?:$| )`) }).click();
}

for (const role of ['reviewer', 'administrator'] as const) {
  test(`${role}: personal pages exclude colleagues while review and archive keep authorized records`, async ({ page }) => {
    // Model the wider API response these roles legitimately receive without changing shared demo data.
    await page.route('**/api/auth/session/', route => route.fulfill({ json: { user: workspace(role).user } }));
    await page.route('**/api/workspace/', route => route.fulfill({ json: workspace(role) }));
    await page.goto('/#dashboard');
    await expect(page.getByRole('heading', { name: /Xayrli kun/ })).toBeVisible();
    const values = page.locator('.stats-grid .stat-value');
    await expect(values).toHaveText(['01', '01', '01', '00']);
    await expect(page.locator('.recent-reports')).toContainText('O‘zimning qoralamam');
    await expect(page.locator('.recent-reports')).not.toContainText('Hamkasbning');

    await navigate(page, 'Shaxsiy portfel');
    await expect(page.locator('.sp-activity-card')).toHaveCount(1);
    await expect(page.locator('.sp-activity-card')).toContainText('O‘zimning maqolam');
    await expect(page.locator('.sp-count')).toHaveText('1');
    await expect(page.locator('.sp-category-card').first().locator('strong')).toHaveText('1ta ish');

    await navigate(page, 'Hisobotlarim');
    await expect(page.locator('.reports-full-table tbody tr')).toHaveCount(2);
    await expect(page.locator('.reports-full-table')).not.toContainText('Hamkasbning');
    await expect(page.getByRole('button', { name: /qoralamasini o‘chirish/ })).toHaveCount(1);
    await expect(page.getByRole('button', { name: 'O‘zimning qoralamam qoralamasini o‘chirish' })).toBeVisible();

    await navigate(page, 'Tekshiruv markazi');
    await expect(page.locator('.reports-full-table tbody tr')).toHaveCount(1);
    await expect(page.locator('.reports-full-table')).toContainText('Hamkasbning tekshiruvdagi hisoboti');

    await navigate(page, 'Arxiv');
    await expect(page.locator('.reports-full-table tbody tr')).toHaveCount(2);
    await expect(page.locator('.reports-full-table')).toContainText('Hamkasbning arxivdagi hisoboti');
  });
}
