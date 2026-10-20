import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowUpRight, CalendarDays, Check, CheckCircle2, CircleDashed, Flag, LoaderCircle, Pencil, Plus, Target, Trash2 } from 'lucide-react';
import { api, dateLabel, patch, post } from '../api';
import type { ActivityCategory, PageProps, WorkItem } from '../types';
import { categoryLabels } from '../types';
import { SupportingModal } from './Portfolio';
import './supporting-pages.css';

export default function WorkPlan({ workspace, onRefresh, toast }: PageProps) {
  const [editor, setEditor] = useState<WorkItem | 'new' | null>(null);
  const [filter, setFilter] = useState('all');
  const totalTarget = workspace.work_items.reduce((sum, item) => sum + item.target, 0);
  const totalCompleted = workspace.work_items.reduce((sum, item) => sum + item.completed, 0);
  const progress = totalTarget ? Math.round(totalCompleted / totalTarget * 100) : 0;
  const completedItems = workspace.work_items.filter(item => item.completed >= item.target).length;
  const items = workspace.work_items.filter(item => filter === 'all' || (filter === 'completed' ? item.completed >= item.target : item.completed < item.target));
  return <>
    <section className="sp-plan-banner"><div className="sp-plan-banner-icon"><Target size={32} /></div><div><span className="sp-plan-eyebrow">SHAXSIY RIVOJLANISH</span><h2>Har bir natija — maqsad sari qadam</h2><p>Rejalashtirilgan ishlaringizni belgilang va bajarilishini kuzating.</p></div><div className="sp-plan-ring" style={{ background: `conic-gradient(#b9b3ff ${progress * 3.6}deg, #ffffff25 0)` }}><div><strong>{progress}%</strong><span>bajarildi</span></div></div></section>
    <div className="sp-plan-stats"><div className="card"><span className="sp-category-icon sp-tone-article"><Flag size={20} /></span><div><small>Jami rejalashtirilgan ishlar</small><strong>{workspace.work_items.length}<span>ta yo‘nalish</span></strong></div></div><div className="card"><span className="sp-category-icon sp-tone-certificate"><CheckCircle2 size={20} /></span><div><small>To‘liq bajarilgan</small><strong>{completedItems}<span>ta yo‘nalish</span></strong></div></div><div className="card"><span className="sp-category-icon sp-tone-conference"><CircleDashed size={20} /></span><div><small>Jarayondagi ishlar</small><strong>{workspace.work_items.length - completedItems}<span>ta yo‘nalish</span></strong></div></div></div>
    <section className="card sp-work-plan"><div className="sp-section-toolbar"><div><h2>Individual ish rejam</h2><p>O‘quv, ilmiy va kasbiy faoliyat bo‘yicha maqsadlaringiz.</p></div><button className="btn primary" onClick={() => setEditor('new')}><Plus size={17} />Reja qo‘shish</button></div><div className="sp-plan-tabs" role="group" aria-label="Rejalarni filtrlash">{[{ value: 'all', label: 'Barcha rejalar' }, { value: 'active', label: 'Jarayonda' }, { value: 'completed', label: 'Bajarilgan' }].map(item => <button key={item.value} className={filter === item.value ? 'active' : ''} onClick={() => setFilter(item.value)} aria-pressed={filter === item.value}>{item.label}</button>)}</div><div className="sp-plan-items">{items.map(item => { const percent = item.target ? Math.min(100, Math.round(item.completed / item.target * 100)) : 0; return <div className="sp-plan-item" key={item.id}><div className={`sp-plan-check ${percent === 100 ? 'done' : ''}`}>{percent === 100 ? <Check size={19} /> : <Target size={19} />}</div><div className="sp-plan-item-main"><div><span className="sp-activity-type">{categoryLabels[item.category as ActivityCategory] ?? item.category}</span><h3>{item.title}</h3></div><span className="sp-plan-date"><CalendarDays size={14} />{dateLabel(item.due_date)}</span><div className="sp-plan-progress-row"><div className={`sp-progress ${percent === 100 ? 'sp-progress-green' : ''}`}><span style={{ width: `${percent}%` }} /></div><span>{item.completed} / {item.target}</span><strong>{percent}%</strong></div></div><button className="btn icon-btn" aria-label={`${item.title} rejasini tahrirlash`} onClick={() => setEditor(item)}><Pencil size={16} /></button></div>; })}</div>{items.length === 0 && <div className="empty-state sp-empty"><Target size={38} /><h3>{filter === 'all' ? 'Birinchi maqsadingizni belgilang' : 'Bu bo‘limda rejalar yo‘q'}</h3><p>{filter === 'all' ? 'Bajariladigan ishlar va muddatlarni kiriting.' : 'Rejalaringiz bajarilish holatiga qarab shu yerda ko‘rinadi.'}</p><button className="btn secondary" onClick={() => filter === 'all' ? setEditor('new') : setFilter('all')}>{filter === 'all' ? 'Reja qo‘shish' : 'Barcha rejalarni ko‘rish'}<ArrowUpRight size={15} /></button></div>}<div className="sp-list-footer"><Target size={15} /><span>Bu yerda shaxsiy rejangizni yuritasiz. Rasmiy tasdiqlash hisobotlar orqali bajariladi.</span></div></section>
    {editor && <PlanEditor item={editor === 'new' ? null : editor} onClose={() => setEditor(null)} onSaved={async message => { await onRefresh(); setEditor(null); toast(message); }} />}
  </>;
}

function PlanEditor({ item, onClose, onSaved }: { item: WorkItem | null; onClose: () => void; onSaved: (message: string) => Promise<void> }) {
  const [form, setForm] = useState({ title: item?.title ?? '', category: item?.category ?? 'article', target: String(item?.target ?? 1), completed: String(item?.completed ?? 0), due_date: item?.due_date ?? '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  async function save(event: FormEvent) {
    event.preventDefault(); setError('');
    if (Number(form.completed) > Number(form.target)) { setError('Bajarilgan ishlar soni rejalashtirilgan miqdordan oshmasligi kerak.'); return; }
    setBusy(true);
    try { const payload = { ...form, title: form.title.trim(), target: Number(form.target), completed: Number(form.completed) }; if (item) await patch(`work-items/${item.id}/`, payload); else await post('work-items/', payload); await onSaved(item ? 'Ish rejangiz yangilandi.' : 'Yangi ish rejasi qo‘shildi.'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Rejani saqlab bo‘lmadi.'); }
    finally { setBusy(false); }
  }
  async function remove() {
    if (!item) return;
    setBusy(true); setError('');
    try { await api(`work-items/${item.id}/`, { method: 'DELETE' }); await onSaved('Ish rejasi o‘chirildi.'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Rejani o‘chirib bo‘lmadi.'); }
    finally { setBusy(false); }
  }
  return <SupportingModal title={item ? 'Ish rejasini tahrirlash' : 'Yangi ish rejasi'} subtitle="Aniq maqsad va bajarish muddatini belgilang." onClose={() => { if (!busy) onClose(); }}><form onSubmit={save}><div className="modal-body sp-form-stack"><label className="field">Reja nomi *<input className="input" required maxLength={240} placeholder="Masalan, xalqaro jurnalda maqola chop etish" value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} /></label><div className="form-grid"><label className="field">Faoliyat turi<select className="input" value={form.category} onChange={event => setForm({ ...form, category: event.target.value })}>{Object.entries(categoryLabels).map(([key, label]) => <option value={key} key={key}>{label}</option>)}</select></label><label className="field">Bajarish muddati *<input className="input" required type="date" value={form.due_date} onChange={event => setForm({ ...form, due_date: event.target.value })} /></label><label className="field">Rejalashtirilgan miqdor<input className="input" type="number" required min={1} max={100000} step={1} value={form.target} onChange={event => setForm({ ...form, target: event.target.value })} /></label><label className="field">Bajarilgan miqdor<input className="input" type="number" required min={0} max={Number(form.target)} step={1} value={form.completed} onChange={event => setForm({ ...form, completed: event.target.value })} /></label></div>{error && <p className="form-error" role="alert">{error}</p>}{confirmDelete && <div className="sp-delete-confirm"><p>Ushbu ish rejasini o‘chirishni tasdiqlaysizmi?</p><button type="button" className="btn danger small" disabled={busy} onClick={remove}>Ha, o‘chirish</button><button type="button" className="btn secondary small" onClick={() => setConfirmDelete(false)}>Bekor qilish</button></div>}</div><div className="modal-footer">{item && <button type="button" className="btn danger sp-delete-left" disabled={busy} onClick={() => setConfirmDelete(true)}><Trash2 size={15} />O‘chirish</button>}<button type="button" className="btn secondary" disabled={busy} onClick={onClose}>Bekor qilish</button><button className="btn primary" type="submit" disabled={busy}>{busy ? <LoaderCircle size={16} className="sp-spin" /> : <Check size={16} />}{busy ? 'Saqlanmoqda...' : 'Rejani saqlash'}</button></div></form></SupportingModal>;
}
