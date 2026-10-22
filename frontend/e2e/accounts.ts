import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, type Page } from '@playwright/test';
export function credentials(role:'employee'|'reviewer'|'administrator'){
  return JSON.parse(readFileSync(resolve(import.meta.dirname,'../../.local/e2e/accounts.json'),'utf8'))[role] as {username:string;password:string};
}
export async function loginAs(page:Page,role:'employee'|'reviewer'|'administrator'){
  await page.goto('/');
  await expect(page.locator('#username, .topbar-user').first()).toBeVisible();
  if(await page.locator('.topbar-user').isVisible()){
    await page.locator('.topbar-user').click();
    await page.getByRole('button',{name:'Chiqish',exact:true}).click();
  }
  await expect(page.getByLabel('Foydalanuvchi nomi')).toBeVisible();
  const account=credentials(role);
  await page.getByLabel('Foydalanuvchi nomi').fill(account.username);
  await page.getByLabel('Parol',{exact:true}).fill(account.password);
  await page.getByRole('button',{name:'Kabinetga kirish'}).click();
  await expect(page.getByRole('heading',{name:/Xayrli kun/})).toBeVisible();
}
