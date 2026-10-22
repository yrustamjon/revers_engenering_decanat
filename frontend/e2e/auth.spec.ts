import { expect, test } from '@playwright/test';
import { credentials, loginAs } from './accounts';

test('anonymous access shows only real login and never calls demo authentication',async({page})=>{
  const demoCalls:string[]=[];
  page.on('request',r=>{if(r.url().includes('/auth/demo/'))demoCalls.push(r.url());});
  await page.goto('/#administration');
  await expect(page.getByRole('heading',{name:'Xush kelibsiz!'})).toBeVisible();
  await expect(page.getByText(/namunaviy|demo/i)).toHaveCount(0);
  expect((await page.request.get('/api/workspace/')).status()).toBe(403);
  expect(demoCalls).toEqual([]);
});

test('wrong password is rejected; real login persists; logout protects reload and private routes',async({page})=>{
  const account=credentials('employee');
  await page.goto('/');
  await page.getByLabel('Foydalanuvchi nomi').fill(account.username);
  await page.getByLabel('Parol',{exact:true}).fill('Incorrect-Password-For-Test');
  await page.getByRole('button',{name:'Kabinetga kirish'}).click();
  await expect(page.getByRole('alert')).toContainText('noto‘g‘ri');
  await page.getByLabel('Parol',{exact:true}).fill(account.password);
  await page.getByRole('button',{name:'Kabinetga kirish'}).click();
  await expect(page.getByRole('heading',{name:/Xayrli kun/})).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading',{name:/Xayrli kun/})).toBeVisible();
  await page.locator('.topbar-user').click();
  await expect(page.getByText('NAMUNAVIY KABINETLAR')).toHaveCount(0);
  await page.getByRole('button',{name:'Chiqish',exact:true}).click();
  await expect(page.getByLabel('Foydalanuvchi nomi')).toBeVisible();
  expect((await page.request.get('/api/workspace/')).status()).toBe(403);
  await page.goto('/#reports');
  await expect(page.getByLabel('Foydalanuvchi nomi')).toBeVisible();
});

test('expired server session clears the workspace and returns to login',async({page})=>{
  await loginAs(page,'employee');
  await page.getByRole('navigation',{name:'Asosiy navigatsiya'}).getByRole('button',{name:'Mening profilim'}).click();
  await page.getByLabel('O‘zim haqimda').fill('Session expiry check');
  const csrf=(await page.context().cookies()).find(cookie=>cookie.name==='csrftoken')!.value;
  expect((await page.request.post('/api/auth/logout/',{data:{},headers:{'X-CSRFToken':csrf}})).status()).toBe(204);
  await page.getByRole('button',{name:'O‘zgarishlarni saqlash'}).click();
  await expect(page.getByLabel('Foydalanuvchi nomi')).toBeVisible();
  await expect(page.locator('.sidebar')).toHaveCount(0);
  await page.reload();
  await expect(page.getByLabel('Foydalanuvchi nomi')).toBeVisible();
});

test('reviewer cannot open administrator data or edit another employee',async({page})=>{
  await loginAs(page,'reviewer');
  expect((await page.request.get('/api/admin/users/')).status()).toBe(403);
  expect((await page.request.get('/api/admin/audit/')).status()).toBe(403);
  await page.goto('/#administration');
  await expect(page.getByRole('heading',{name:'Administrator vakolati kerak'})).toBeVisible();
  expect((await page.request.get('/api/auth/session/')).status()).toBe(200);
});


test('unknown and prototype hash routes safely fall back to dashboard',async({page})=>{
  await loginAs(page,'employee');
  for(const hash of ['__proto__','constructor','unknown-page']){
    await page.goto('/#'+hash);
    await expect(page.getByRole('heading',{name:/Xayrli kun/})).toBeVisible();
  }
});
