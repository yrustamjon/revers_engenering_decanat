import { test, expect, type Page } from '@playwright/test';

const nonce = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

async function ready(page: Page) {
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Xayrli kun/ })).toBeVisible();
}

async function navigate(page: Page, name: string) {
  await page.locator('.sidebar-navigation').getByRole('button', { name: new RegExp(`^${name}(?:$| )`) }).click();
}

async function switchRole(page: Page, role: 'employee' | 'reviewer' | 'administrator') {
  await page.locator('.topbar-user').click();
  await page.getByRole('button', { name: role === 'administrator' ? 'Administrator sifatida ko‘rish' : role === 'reviewer' ? 'Tekshiruvchi sifatida ko‘rish' : 'Xodim sifatida ko‘rish' }).click();
  await expect(page.getByRole('heading', { name: role === 'administrator' ? 'Universitet boshqaruvi' : role === 'reviewer' ? 'Tekshiruv markazi' : /Xayrli kun/ })).toBeVisible();
}

async function apiPost(page: Page, path: string, data: unknown, method: 'POST' | 'PATCH' | 'DELETE' = 'POST') {
  const csrf = (await page.context().cookies()).find(cookie => cookie.name === 'csrftoken')?.value;
  return page.request.fetch(`/api/${path}`, { method, data, headers: { 'X-CSRFToken': csrf || '' } });
}

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => {
    const expectedAnonymous = /\/api\/auth\/session\//.test(message.location().url) && /(?:401|403)/.test(message.text());
    if (message.type() === 'error' && !expectedAnonymous) errors.push(`${message.text()} (${message.location().url})`);
  });
  (page as Page & { recordedErrors?: string[] }).recordedErrors = errors;
});

test.afterEach(async ({ page }, testInfo) => {
  const errors = (page as Page & { recordedErrors?: string[] }).recordedErrors || [];
  await testInfo.attach('browser-errors', { body: JSON.stringify(errors, null, 2), contentType: 'application/json' });
  expect(errors, 'Unexpected browser console or JavaScript errors').toEqual([]);
});

test('dashboard, portfolio filters and global search use real records', async ({ page }) => {
  await ready(page);
  await expect(page.getByRole('heading', { name: 'So‘nggi hisobotlar' })).toBeVisible();
  await expect(page.locator('.stats-grid .stat-card')).toHaveCount(4);
  await navigate(page, 'Shaxsiy portfel');
  const cards = page.locator('.sp-activity-card');
  expect(await cards.count()).toBeGreaterThan(0);
  const firstTitle = (await cards.first().locator('h3').innerText()).trim();
  await page.getByLabel('Faoliyatni qidirish').fill(firstTitle);
  await expect(cards).toHaveCount(1);
  await expect(cards.first().locator('h3')).toHaveText(firstTitle);
  await page.getByLabel('Faoliyatni qidirish').fill('HechQachonTopilmaydiganE2E');
  await expect(page.getByRole('heading', { name: 'Mos faoliyat topilmadi' })).toBeVisible();
  await page.getByRole('button', { name: 'Filtrlarni tozalash' }).click();
  await page.getByLabel('Faoliyat turi', { exact: true }).selectOption('certificate');
  for (const card of await cards.all()) await expect(card.locator('.sp-activity-type')).toHaveText('Sertifikat');
  await page.getByLabel('Platformada qidirish').fill(firstTitle);
  await page.locator('.search-results').getByRole('button', { name: new RegExp(firstTitle.slice(0, 18)) }).click();
  await expect(page.getByLabel('Faoliyatni qidirish')).toHaveValue(firstTitle);
  await expect(cards).toHaveCount(1);
});

test('evidence upload and report return, correction, resubmission, approval and archive', async ({ page }) => {
  const activityTitle = `E2E dalilli ilmiy maqola ${nonce}`;
  const reportTitle = `E2E ilmiy hisobot ${nonce}`;
  const returnComment = 'Maqolaning nashr sanasini hisobot davri bilan solishtiring va davrni aniqlashtiring.';
  await ready(page);
  await page.getByRole('button', { name: 'Faoliyat qo‘shish', exact: true }).first().click();
  let dialog = page.getByRole('dialog');
  await expect(dialog).toHaveAttribute('aria-label', 'Yangi faoliyat qo‘shish');
  await dialog.getByRole('textbox', { name: 'Faoliyat nomi *' }).fill(activityTitle);
  await dialog.getByLabel('Qisqacha tavsif').fill('Brauzer orqali fayl yuklash va to‘liq hisobot aylanishi uchun sinov dalili.');
  await dialog.getByLabel('Tasdiqlovchi hujjatni tanlash').setInputFiles({ name: `e2e-evidence-${nonce}.txt`, mimeType: 'text/plain', buffer: Buffer.from('UniFlow E2E evidence. Illustrative test data, not an institutional record.') });
  await dialog.getByRole('button', { name: 'Faoliyatni saqlash' }).click();
  await expect(dialog).toHaveCount(0);
  await page.locator('.sp-activity-card').filter({ hasText: activityTitle }).click();
  dialog = page.getByRole('dialog');
  const attachment = dialog.getByRole('link', { name: new RegExp(`e2e-evidence-${nonce}`) });
  await expect(attachment).toBeVisible();
  const download = await page.request.get((await attachment.getAttribute('href'))!);
  expect(download.ok()).toBeTruthy();
  expect(await download.text()).toContain('UniFlow E2E evidence');
  await dialog.getByRole('button', { name: 'Yopish', exact: true }).click();

  await navigate(page, 'Hisobotlarim');
  await page.getByRole('button', { name: 'Yangi hisobot', exact: true }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Hisobot nomi').fill(reportTitle);
  await dialog.getByLabel('Hisobot davri').fill('2026-yil, E2E sinov davri');
  await dialog.getByRole('checkbox', { name: new RegExp(activityTitle) }).check();
  await dialog.getByRole('button', { name: 'Tekshirishga yuborish' }).click();
  await expect(dialog.getByText('Tekshirilmoqda', { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Yopish', exact: true }).click();

  await switchRole(page, 'reviewer');
  await page.locator('.table-title-button').filter({ hasText: reportTitle }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Qaytarish', exact: true }).click();
  await dialog.getByLabel('Qaysi bandni qanday tuzatish kerak?').fill(returnComment);
  await dialog.getByRole('button', { name: 'Izoh bilan qaytarish' }).click();
  await expect(dialog.getByText('Tuzatish kerak', { exact: true })).toBeVisible();
  await expect(dialog.locator('.return-comment')).toContainText(returnComment);
  await dialog.getByRole('button', { name: 'Yopish', exact: true }).click();

  await switchRole(page, 'employee');
  await navigate(page, 'Hisobotlarim');
  await page.locator('.table-title-button').filter({ hasText: reportTitle }).click();
  dialog = page.getByRole('dialog');
  await expect(dialog.locator('.return-comment')).toContainText(returnComment);
  await dialog.getByRole('button', { name: 'Tahrirlash', exact: true }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Hisobot davri').fill('2026-yil, aniqlashtirilgan davr');
  await dialog.getByRole('button', { name: 'Tekshirishga yuborish' }).click();
  await expect(dialog.getByText('Tekshirilmoqda', { exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Yopish', exact: true }).click();

  await switchRole(page, 'reviewer');
  await page.locator('.table-title-button').filter({ hasText: reportTitle }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'Tasdiqlash', exact: true }).click();
  await dialog.getByLabel('Tasdiqlash izohi (ixtiyoriy)').fill('Dalillar va hisobot davri tekshirildi.');
  await dialog.getByRole('button', { name: 'Tasdiqlashni yakunlash' }).click();
  await expect(dialog.getByText('Tasdiqlangan', { exact: true })).toBeVisible();
  await expect(dialog.locator('.history-list')).toContainText(returnComment);
  await expect(dialog.getByRole('button', { name: 'PDF / Chop etish' })).toBeVisible();
  const popupPromise = page.waitForEvent('popup');
  await dialog.getByRole('button', { name: 'PDF / Chop etish' }).click();
  const popup = await popupPromise;
  await expect(popup.getByRole('heading', { name: reportTitle })).toBeVisible();
  await expect(popup.getByRole('cell', { name: activityTitle, exact: true })).toBeVisible();
  await popup.close();
  await dialog.getByRole('button', { name: 'Yopish', exact: true }).click();
  await switchRole(page, 'employee');
  await navigate(page, 'Arxiv');
  await expect(page.locator('.table-title-button').filter({ hasText: reportTitle })).toBeVisible();
  await navigate(page, 'Shaxsiy portfel');
  await page.locator('.sp-activity-card').filter({ hasText: activityTitle }).click();
  dialog = page.getByRole('dialog');
  await expect(dialog.getByRole('button', { name: 'Tahrirlash', exact: true })).toBeDisabled();
  await expect(dialog.getByRole('button', { name: 'O‘chirish', exact: true })).toBeDisabled();
});

test('profile changes persist and work plan supports create, update and delete', async ({ page }) => {
  await ready(page);
  await navigate(page, 'Mening profilim');
  const bio = page.getByLabel('O‘zim haqimda');
  const originalBio = await bio.inputValue();
  const changedBio = `E2E profilni saqlash tekshiruvi ${nonce}`;
  await bio.fill(changedBio);
  await page.getByRole('button', { name: 'O‘zgarishlarni saqlash' }).click();
  await expect(page.getByRole('status')).toContainText('Profil ma’lumotlari saqlandi');
  await page.reload();
  await expect(page.getByLabel('O‘zim haqimda')).toHaveValue(changedBio);
  await page.getByLabel('O‘zim haqimda').fill(originalBio);
  await page.getByRole('button', { name: 'O‘zgarishlarni saqlash' }).click();
  await expect(page.getByRole('status')).toContainText('Profil ma’lumotlari saqlandi');

  await navigate(page, 'Ish rejam');
  const planTitle = `E2E individual reja ${nonce}`;
  await page.getByRole('button', { name: 'Reja qo‘shish', exact: true }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByRole('textbox', { name: 'Reja nomi *' }).fill(planTitle);
  await dialog.getByLabel('Bajarish muddati').fill('2026-12-31');
  await dialog.getByLabel('Rejalashtirilgan miqdor').fill('3');
  await dialog.getByLabel('Bajarilgan miqdor').fill('1');
  await dialog.getByRole('button', { name: 'Rejani saqlash' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  let item = page.locator('.sp-plan-item').filter({ hasText: planTitle });
  await expect(item).toContainText('1 / 3');
  await item.getByRole('button', { name: `${planTitle} rejasini tahrirlash` }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('Bajarilgan miqdor').fill('3');
  await dialog.getByRole('button', { name: 'Rejani saqlash' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  item = page.locator('.sp-plan-item').filter({ hasText: planTitle });
  await expect(item).toContainText('100%');
  await item.getByRole('button', { name: `${planTitle} rejasini tahrirlash` }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: 'O‘chirish', exact: true }).click();
  await dialog.getByRole('button', { name: 'Ha, o‘chirish' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.sp-plan-item').filter({ hasText: planTitle })).toHaveCount(0);
});

test('mobile navigation and primary pages fit a 390px viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  async function assertNoHorizontalOverflow() {
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBeTruthy();
  }
  await assertNoHorizontalOverflow();
  for (const [nav, heading] of [['Shaxsiy portfel', 'Shaxsiy portfel'], ['Hisobotlarim', 'Hisobotlarim'], ['Ish rejam', 'Shaxsiy ish rejam'], ['Shablonlar', 'Tayyor shablonlar'], ['Mening profilim', 'Mening profilim']]) {
    await page.getByRole('button', { name: 'Menyuni ochish' }).click();
    await navigate(page, nav);
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    await assertNoHorizontalOverflow();
  }
});

test('administrator provisions a real account, password changes preserve session, deactivation blocks access', async ({ page, browser }) => {
  const departmentName = `E2E kafedra ${nonce}`;
  const fullName = `E2E Haqiqiy Xodim ${nonce}`;
  const username = `e2e_user_${nonce}`;
  // These public constants are test fixtures, never production credentials.
  const initialPassword = 'Compass!Larch92River';
  const changedPassword = 'Another!Birch39Forest';
  await ready(page);
  await switchRole(page, 'administrator');
  await page.getByRole('tab', { name: /^Tuzilma/ }).click();
  await page.getByRole('button', { name: 'Bo‘lim qo‘shish' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('Bo‘lim nomi').fill(departmentName);
  await dialog.getByLabel('Fakultet / yuqori bo‘linma').fill('E2E sinov fakulteti');
  await dialog.getByLabel('Mas’ul xodim').fill('Sinov Mas’uli');
  await dialog.getByRole('button', { name: 'Bo‘limni saqlash' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.ad-department-card').filter({ hasText: departmentName })).toBeVisible();
  await page.getByRole('tab', { name: /^Xodimlar/ }).click();
  await page.getByRole('button', { name: 'Xodim qo‘shish' }).click();
  dialog = page.getByRole('dialog');
  await dialog.getByLabel('To‘liq ism-familiya').fill(fullName);
  await dialog.getByLabel('Elektron pochta').fill(`${username}@example.com`);
  await dialog.getByLabel('Login').fill(username);
  await dialog.getByLabel('Boshlang‘ich parol').fill(initialPassword);
  await dialog.getByLabel('Kafedra / bo‘lim').selectOption({ label: departmentName });
  await dialog.getByLabel('Lavozim').fill('O‘qituvchi');
  await dialog.getByLabel('Xodim ID').fill(`E2E-${Date.now()}`);
  await dialog.getByLabel('Tizimdagi rol').selectOption('employee');
  await dialog.getByRole('button', { name: 'Xodimni yaratish' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const row = page.locator('.ad-table tbody tr').filter({ hasText: username });
  await expect(row).toContainText('Faol');
  await expect(row).toContainText(departmentName);

  const employeeContext = await browser.newContext({ baseURL: new URL(page.url()).origin });
  const employee = await employeeContext.newPage();
  const errors = (page as Page & { recordedErrors?: string[] }).recordedErrors!;
  employee.on('pageerror', error => errors.push(error.message));
  employee.on('console', message => {
    const anonymous = /\/api\/auth\/session\//.test(message.location().url) && /(?:401|403)/.test(message.text());
    if (message.type() === 'error' && !anonymous) errors.push(`${message.text()} (${message.location().url})`);
  });
  try {
    await ready(employee);
    await employee.locator('.topbar-user').click();
    await employee.getByRole('button', { name: 'Chiqish', exact: true }).click();
    await expect(employee.getByRole('heading', { name: 'Xush kelibsiz!' })).toBeVisible();
    await employee.getByLabel('Foydalanuvchi nomi').fill(username);
    await employee.getByLabel('Parol', { exact: true }).fill(initialPassword);
    await employee.getByRole('button', { name: 'Kabinetga kirish' }).click();
    await expect(employee.locator('.topbar-user')).toContainText(fullName);
    await expect(employee.locator('.topbar-user')).toHaveAttribute('aria-expanded', 'false');
    await employee.locator('.topbar-user').click();
    await expect(employee.getByRole('button', { name: 'Administrator sifatida ko‘rish' })).toHaveCount(0);
    await employee.getByRole('button', { name: 'Parolni o‘zgartirish' }).click();
    let employeeDialog = employee.getByRole('dialog');
    await employeeDialog.getByLabel('Amaldagi parol').fill(initialPassword);
    await employeeDialog.getByLabel('Yangi parol', { exact: true }).fill(changedPassword);
    await employeeDialog.getByLabel('Yangi parolni takrorlang').fill(changedPassword);
    await employeeDialog.getByRole('button', { name: 'Parolni yangilash' }).click();
    await expect(employee.getByRole('dialog')).toHaveCount(0);
    await expect(employee.getByRole('status')).toContainText('Parolingiz yangilandi');
    await employee.reload();
    await expect(employee.locator('.topbar-user')).toContainText(fullName);
    await navigate(employee, 'Mening profilim');
    await expect(employee.locator('.sp-employment-grid')).toContainText(departmentName);
    await employee.getByLabel('Telefon raqami').fill('+998 90 111 22 33');
    await employee.getByRole('button', { name: 'O‘zgarishlarni saqlash' }).click();
    await employee.reload();
    await expect(employee.getByLabel('Telefon raqami')).toHaveValue('+998 90 111 22 33');

    await row.getByRole('button', { name: `${fullName} hisobini nofaol qilish` }).click();
    dialog = page.getByRole('dialog');
    await dialog.getByRole('button', { name: 'Nofaol qilish', exact: true }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
    await expect(row).toContainText('Nofaol');
    expect((await employee.request.get('/api/workspace/')).status()).toBe(403);
    const login = await apiPost(employee, 'auth/login/', { username, password: changedPassword });
    expect(login.status()).toBe(401);
  } finally {
    await employeeContext.close();
    const users = await (await page.request.get('/api/admin/users/')).json();
    const created = users.find((user: { username: string }) => user.username === username);
    if (created?.is_active) expect((await apiPost(page, `admin/users/${created.id}/`, { is_active: false }, 'PATCH')).ok()).toBeTruthy();
  }
});

test('administrator-defined required template fields are validated, preserved and printed', async ({ page }) => {
  const templateId = `e2e-schema-${nonce}`;
  const templateTitle = `E2E maxsus ilmiy shakl ${nonce}`;
  const reportTitle = `E2E maxsus maydonli hisobot ${nonce}`;
  const fieldLabel = 'Tadqiqotning qisqa mazmuni';
  const fieldValue = `Universitetdagi hujjat aylanishini tekshirish natijalari ${nonce}.`;
  let reportId: number | undefined;
  await ready(page);
  await switchRole(page, 'administrator');
  await page.getByRole('tab', { name: /^Shablonlar/ }).click();
  await page.getByRole('button', { name: 'Shablon qo‘shish' }).click();
  let dialog = page.getByRole('dialog');
  await dialog.getByLabel('Shablon identifikatori').fill(templateId);
  await dialog.getByLabel('Shablon nomi').fill(templateTitle);
  await dialog.getByLabel('Tavsif', { exact: true }).fill('Majburiy maxsus maydon va shablon nusxasini sinash uchun shakl.');
  await dialog.getByLabel('Hisobot tarkibi').fill('Ilmiy natijalar\nTasdiqlovchi dalillar');
  await dialog.getByRole('button', { name: 'Maydon', exact: true }).click();
  await dialog.getByLabel('Maydon nomi').fill(fieldLabel);
  await dialog.getByLabel('Kalit').fill('research_summary');
  await dialog.getByLabel('Maydon turi').selectOption('textarea');
  await dialog.getByLabel('To‘ldirish majburiy').check();
  await dialog.getByRole('button', { name: 'Shablonni saqlash' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.ad-template-card').filter({ hasText: templateTitle })).toBeVisible();
  try {
    await switchRole(page, 'employee');
    await navigate(page, 'Shablonlar');
    await page.locator('.template-card').filter({ hasText: templateTitle }).getByRole('button', { name: 'Shablondan foydalanish' }).click();
    dialog = page.getByRole('dialog');
    await expect(dialog.getByLabel(fieldLabel)).toBeVisible();
    await dialog.getByLabel('Hisobot nomi').fill(reportTitle);
    await dialog.getByLabel('Hisobot davri').fill('2026-yil, shablon sinovi');
    await dialog.getByRole('checkbox').first().check();
    await dialog.getByRole('button', { name: 'Tekshirishga yuborish' }).click();
    await expect(dialog.getByRole('alert')).toContainText(fieldLabel);
    await expect(dialog.getByRole('alert')).toContainText('to‘ldiring');
    await dialog.getByLabel(fieldLabel).fill(fieldValue);
    await dialog.getByRole('button', { name: 'Tekshirishga yuborish' }).click();
    await expect(dialog.getByText('Tekshirilmoqda', { exact: true })).toBeVisible();
    await expect(dialog.locator('.report-custom-values')).toContainText(fieldLabel);
    await expect(dialog.locator('.report-custom-values')).toContainText(fieldValue);
    const workspace = await (await page.request.get('/api/workspace/')).json();
    const report = workspace.reports.find((item: { title: string }) => item.title === reportTitle);
    reportId = report.id;
    expect(report.template_snapshot.id).toBe(templateId);
    expect(report.template_snapshot.version).toBe('1.0');
    expect(report.extra_data.research_summary).toBe(fieldValue);
    const popupPromise = page.waitForEvent('popup');
    await dialog.getByRole('button', { name: 'Qoralama nusxasi' }).click();
    const popup = await popupPromise;
    await expect(popup.locator('body')).toContainText(fieldLabel);
    await expect(popup.locator('body')).toContainText(fieldValue);
    await popup.close();
    await dialog.getByRole('button', { name: 'Yopish', exact: true }).click();
    await switchRole(page, 'administrator');
    expect((await apiPost(page, `reports/${reportId}/review/`, { decision: 'returned', comment: 'E2E shakl sinovi tugadi; test yozuvini tozalash uchun qaytarildi.' })).ok()).toBeTruthy();
  } finally {
    // Submitted data is returned through the supported workflow before removal.
    const current = await (await page.request.get('/api/workspace/')).json();
    if (current.user.role !== 'administrator') {
      expect((await apiPost(page, 'auth/demo/', { role: 'administrator' })).ok()).toBeTruthy();
    }
    if (reportId) {
      const reportResponse = await page.request.get(`/api/reports/${reportId}/`);
      if (reportResponse.ok() && (await reportResponse.json()).status === 'submitted') {
        expect((await apiPost(page, `reports/${reportId}/review/`, { decision: 'returned', comment: 'E2E maxsus shablon sinovi tugadi.' })).ok()).toBeTruthy();
      }
    }
    expect((await apiPost(page, `admin/templates/${templateId}/`, { is_active: false }, 'PATCH')).ok()).toBeTruthy();
    expect((await apiPost(page, 'auth/demo/', { role: 'employee' })).ok()).toBeTruthy();
    if (reportId) expect((await apiPost(page, `reports/${reportId}/`, undefined, 'DELETE')).ok()).toBeTruthy();
  }
});
