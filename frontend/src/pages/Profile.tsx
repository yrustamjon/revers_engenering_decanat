import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Award, BadgeCheck, BookOpen, BriefcaseBusiness, Building2, Check, GraduationCap, LoaderCircle, Mail, Phone, Save, ShieldCheck, UserRound } from 'lucide-react';
import { patch } from '../api';
import type { PageProps } from '../types';
import './supporting-pages.css';

export default function Profile({ workspace, onRefresh, toast }: PageProps) {
  const { profile, activities, reports } = workspace;
  const [form, setForm] = useState({ full_name: profile.full_name, email: profile.email, phone: profile.phone, bio: profile.bio });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { setForm({ full_name: profile.full_name, email: profile.email, phone: profile.phone, bio: profile.bio }); }, [profile]);
  const completionFields = [profile.full_name, profile.email, profile.phone, profile.bio, profile.department, profile.position, profile.degree];
  const completion = Math.round(completionFields.filter(Boolean).length / completionFields.length * 100);
  const changed = form.full_name !== profile.full_name || form.email !== profile.email || form.phone !== profile.phone || form.bio !== profile.bio;
  async function save(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try { await patch('profile/', form); await onRefresh(); toast('Profil ma’lumotlari saqlandi.'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Profilni saqlab bo‘lmadi.'); }
    finally { setBusy(false); }
  }
  return <div className="sp-profile-layout">
    <aside className="sp-profile-sidebar"><section className="card sp-identity-card"><div className="sp-profile-cover"><div className="sp-cover-orbit" /><GraduationCap size={34} /></div><div className="sp-identity-body"><div className="sp-profile-avatar">{profile.initials || profile.full_name.split(' ').map(part => part[0]).slice(0, 2).join('')}<span><Check size={11} strokeWidth={3} /></span></div><h2>{profile.full_name}</h2><p>{profile.position}</p><span className="sp-pill sp-pill-purple"><BadgeCheck size={13} /> {profile.degree || 'Universitet xodimi'}</span><div className="sp-identity-info"><span><Building2 size={16} />{profile.department}</span><span><Mail size={16} />{profile.email || 'Email kiritilmagan'}</span><span><Phone size={16} />{profile.phone || 'Telefon kiritilmagan'}</span></div><div className="sp-profile-stat-row"><div><strong>{activities.length}</strong><span>Faoliyat</span></div><div><strong>{reports.filter(report => report.status === 'approved').length}</strong><span>Tasdiqlangan</span></div><div><strong>{profile.experience_years}</strong><span>Yil tajriba</span></div></div></div></section>
      <section className="card sp-completion-card"><div><span className="sp-category-icon sp-tone-certificate"><UserRound size={19} /></span><strong>Profil to‘liqligi</strong><b>{completion}%</b></div><div className="sp-progress"><span style={{ width: `${completion}%` }} /></div><p>{completion === 100 ? 'Barcha asosiy ma’lumotlaringiz kiritilgan.' : 'Hisobotlar to‘g‘ri shakllanishi uchun ma’lumotlaringizni to‘ldiring.'}</p></section>
    </aside>
    <div className="sp-profile-main"><section className="card"><div className="sp-section-toolbar"><div><h2>Shaxsiy ma’lumotlar</h2><p>Profilingiz va bog‘lanish ma’lumotlarini boshqaring.</p></div><span className="sp-small-label"><UserRound size={15} />Shaxsiy profil</span></div><form className="sp-profile-form" onSubmit={save}><div className="form-grid"><label className="field">To‘liq ism-familiya *<input className="input" required maxLength={150} value={form.full_name} onChange={event => setForm({ ...form, full_name: event.target.value })} /></label><label className="field">Xodim ID<input className="input" value={profile.employee_id} readOnly /><small>Kadrlar bo‘limi tomonidan belgilanadi.</small></label><label className="field">Elektron pochta *<input className="input" type="email" required value={form.email} onChange={event => setForm({ ...form, email: event.target.value })} /></label><label className="field">Telefon raqami<input className="input" type="tel" maxLength={30} placeholder="+998 90 123 45 67" value={form.phone} onChange={event => setForm({ ...form, phone: event.target.value })} /></label></div><label className="field">O‘zim haqimda<textarea className="input" rows={4} maxLength={2000} placeholder="Ilmiy qiziqishlaringiz, mutaxassisligingiz va tajribangiz haqida..." value={form.bio} onChange={event => setForm({ ...form, bio: event.target.value })} /></label>{error && <p className="form-error" role="alert">{error}</p>}<div className="sp-profile-save"><span>{changed ? 'Saqlanmagan o‘zgarishlar bor' : 'Ma’lumotlaringiz yangilangan'}</span><button className="btn primary" type="submit" disabled={busy || !changed}>{busy ? <LoaderCircle size={16} className="sp-spin" /> : <Save size={16} />}{busy ? 'Saqlanmoqda...' : 'O‘zgarishlarni saqlash'}</button></div></form></section>
      <section className="card"><div className="sp-section-toolbar"><div><h2>Ish joyi va malaka</h2><p>Universitet tomonidan tasdiqlangan ma’lumotlar.</p></div><ShieldCheck size={20} className="sp-purple" /></div><div className="sp-employment-grid">{[
        { label: 'Fakultet', value: profile.faculty, icon: Building2 },
        { label: 'Kafedra / bo‘lim', value: profile.department, icon: BookOpen },
        { label: 'Lavozim', value: profile.position, icon: BriefcaseBusiness },
        { label: 'Ilmiy daraja', value: profile.degree, icon: GraduationCap },
        { label: 'Bandlik turi', value: profile.employment_type, icon: BadgeCheck },
        { label: 'Ish tajribasi', value: `${profile.experience_years} yil`, icon: Award },
      ].map(({ label, value, icon: Icon }) => <div className="sp-employment-item" key={label}><span><Icon size={18} /></span><div><small>{label}</small><strong>{value || 'Belgilanmagan'}</strong></div></div>)}</div><div className="sp-verified-note"><ShieldCheck size={15} /><p>Bu ma’lumotlarni o‘zgartirish uchun kadrlar bo‘yicha mas’ul xodimga murojaat qiling.</p></div></section>
    </div>
  </div>;
}
