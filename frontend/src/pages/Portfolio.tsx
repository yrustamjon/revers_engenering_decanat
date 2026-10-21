import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { ArrowDownToLine, ArrowUpRight, Award, BookOpen, CalendarDays, Check, CheckCheck, FileText, FlaskConical, GraduationCap, Link2, LoaderCircle, Pencil, Plus, Search, ShieldCheck, Trash2, UploadCloud, UsersRound, X } from 'lucide-react';
import { api, dateLabel, patch, post } from '../api';
import type { Activity, ActivityCategory, Attachment, PageProps } from '../types';
import { categoryLabels } from '../types';
import './supporting-pages.css';

const categoryIcons = { article: FileText, conference: UsersRound, certificate: Award, teaching: BookOpen, project: FlaskConical };
const categories = Object.keys(categoryLabels) as ActivityCategory[];
const localDate = () => new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
type ActivityForm = { title: string; category: ActivityCategory; date: string; description: string; link: string };

export function SupportingModal({ title, subtitle, children, onClose, className = '' }: { title: string; subtitle?: string; children: ReactNode; onClose: () => void; className?: string }) {
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    panel.current?.querySelector<HTMLElement>('input, select, textarea, button')?.focus();
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close.current();
      if (event.key !== 'Tab') return;
      const elements = panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]');
      if (!elements?.length) return;
      const first = elements[0]; const last = elements[elements.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', handler);
    return () => { document.removeEventListener('keydown', handler); document.body.style.overflow = previousOverflow; previous?.focus(); };
  }, []);
  return <div className="modal-overlay" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
    <div className={`modal sp-modal ${className}`} ref={panel} role="dialog" aria-modal="true" aria-label={title}>
      <div className="modal-header"><div><h2>{title}</h2>{subtitle && <p>{subtitle}</p>}</div><button type="button" className="btn icon-btn" aria-label="Oynani yopish" onClick={onClose}><X size={19} /></button></div>
      {children}
    </div>
  </div>;
}

export default function Portfolio({ workspace, onRefresh, toast }: PageProps) {
  const [category, setCategory] = useState<ActivityCategory | 'all'>('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('newest');
  const [editor, setEditor] = useState<Activity | 'new' | null>(null);
  const [selected, setSelected] = useState<Activity | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [detailError, setDetailError] = useState('');
  const locked = new Set(workspace.reports.filter(report => report.status === 'submitted' || report.status === 'approved').flatMap(report => report.activity_ids));
  const mine = useMemo(() => workspace.activities.filter(activity => activity.owner_id === workspace.user.id), [workspace.activities, workspace.user.id]);
  const filtered = useMemo(() => mine.filter(activity => (category === 'all' || activity.category === category) && `${activity.title} ${activity.description}`.toLocaleLowerCase().includes(query.toLocaleLowerCase())).sort((a, b) => sort === 'name' ? a.title.localeCompare(b.title) : b.date.localeCompare(a.date)), [mine, category, query, sort]);
  useEffect(() => {
    const openRequested = () => {
      if (!window.location.hash.startsWith('#portfolio')) return;
      const params = new URLSearchParams(window.location.hash.split('?')[1] ?? '');
      if (params.has('search')) { setQuery(params.get('search') ?? ''); setCategory('all'); }
      if (params.get('new') === '1') {
        setEditor('new');
        window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}#portfolio`);
      }
    };
    openRequested(); window.addEventListener('hashchange', openRequested);
    return () => window.removeEventListener('hashchange', openRequested);
  }, []);
  const canModifySelected = selected?.owner_id === workspace.user.id;
  const safeLink = selected && /^https?:\/\//i.test(selected.link) ? selected.link : null;
  const openDetail = (activity: Activity) => { setSelected(activity); setConfirmDelete(false); setDetailError(''); };
  async function deleteActivity() {
    if (!selected) return;
    setDeleting(true); setDetailError('');
    try { await api(`activities/${selected.id}/`, { method: 'DELETE' }); await onRefresh(); setSelected(null); toast('Faoliyat portfeldan o‘chirildi.'); }
    catch (error) { setDetailError(error instanceof Error ? error.message : 'Faoliyatni o‘chirib bo‘lmadi.'); }
    finally { setDeleting(false); }
  }
  return <>
    <div className="sp-portfolio-overview">
      {categories.map(key => { const Icon = categoryIcons[key]; return <button key={key} className={`card sp-category-card ${category === key ? 'sp-category-active' : ''}`} onClick={() => setCategory(category === key ? 'all' : key)} aria-pressed={category === key}>
        <span className={`sp-category-icon sp-tone-${key}`}><Icon size={21} /></span><span className="sp-category-name">{categoryLabels[key]}</span><strong>{mine.filter(item => item.category === key).length}<span>ta ish</span></strong>
      </button>; })}
    </div>
    <section className="card sp-portfolio-list">
      <div className="sp-section-toolbar"><div><h2>Faoliyatlarim <span className="sp-count">{mine.length}</span></h2><p>Yutuqlaringiz va ularni tasdiqlovchi hujjatlar bir joyda.</p></div><button className="btn primary" onClick={() => setEditor('new')}><Plus size={17} /> Faoliyat qo‘shish</button></div>
      <div className="sp-list-filters"><div className="sp-search"><Search size={17} /><input aria-label="Faoliyatni qidirish" placeholder="Faoliyat nomi bo‘yicha qidirish..." value={query} onChange={event => setQuery(event.target.value)} /></div><select className="input sp-select" value={category} onChange={event => setCategory(event.target.value as ActivityCategory | 'all')} aria-label="Faoliyat turi"><option value="all">Barcha turlar</option>{categories.map(key => <option value={key} key={key}>{categoryLabels[key]}</option>)}</select><select className="input sp-select" aria-label="Saralash" value={sort} onChange={event => setSort(event.target.value)}><option value="newest">Avval yangilari</option><option value="name">Nomi bo‘yicha</option></select></div>
      <div className="sp-activity-grid">
        {filtered.map(activity => { const Icon = categoryIcons[activity.category]; return <button className="sp-activity-card" key={activity.id} onClick={() => openDetail(activity)}>
          <div className="sp-activity-top"><span className={`sp-category-icon sp-tone-${activity.category}`}><Icon size={21} /></span><span className={`sp-pill ${activity.status === 'verified' ? 'sp-pill-green' : 'sp-pill-gray'}`}>{activity.status === 'verified' ? <><CheckCheck size={12} /> Tasdiqlangan</> : 'Kiritilgan'}</span></div>
          <span className="sp-activity-type">{categoryLabels[activity.category]}</span><h3>{activity.title}</h3><p className="sp-activity-description">{activity.description || 'Tavsif kiritilmagan.'}</p>
          <div className="sp-activity-bottom"><span><CalendarDays size={13} />{dateLabel(activity.date)}</span><span className="sp-detail-link">Batafsil <ArrowUpRight size={15} /></span></div>
        </button>; })}
      </div>
      {filtered.length === 0 && <div className="empty-state sp-empty"><GraduationCap size={38} /><h3>{query || category !== 'all' ? 'Mos faoliyat topilmadi' : 'Portfelingizni yarating'}</h3><p>{query || category !== 'all' ? 'Boshqa so‘z yoki faoliyat turini tanlab ko‘ring.' : 'Maqola, sertifikat va bajargan ishlaringizni birinchi bo‘lib qo‘shing.'}</p><button className="btn secondary" onClick={() => { if (query || category !== 'all') { setQuery(''); setCategory('all'); } else setEditor('new'); }}>{query || category !== 'all' ? 'Filtrlarni tozalash' : 'Faoliyat qo‘shish'}</button></div>}
      <div className="sp-list-footer"><ShieldCheck size={15} /><span>Ma’lumotlaringiz faqat siz va vakolatli mas’ullarga ko‘rinadi.</span><span>{filtered.length} ta faoliyat</span></div>
    </section>
    {editor && <ActivityEditor activity={editor === 'new' ? null : editor} onClose={() => setEditor(null)} onSaved={async () => { await onRefresh(); setEditor(null); toast(editor === 'new' ? 'Yangi faoliyat portfelga qo‘shildi.' : 'Faoliyat ma’lumotlari yangilandi.'); }} />}
    {selected && <SupportingModal title="Faoliyat tafsilotlari" subtitle={categoryLabels[selected.category]} onClose={() => setSelected(null)}>
      <div className="modal-body"><span className={`sp-pill ${selected.status === 'verified' ? 'sp-pill-green' : 'sp-pill-gray'}`}>{selected.status === 'verified' ? 'Tasdiqlangan' : 'Kiritilgan'}</span><h3 className="sp-detail-title">{selected.title}</h3><div className="sp-detail-meta"><span><CalendarDays size={15} />{dateLabel(selected.date)}</span><span>{selected.owner_name}</span></div><p className="sp-detail-description">{selected.description || 'Tavsif kiritilmagan.'}</p>
        {safeLink && <a className="sp-resource-link" href={safeLink} target="_blank" rel="noreferrer"><Link2 size={17} /><span>Manba havolasi<small>{selected.link}</small></span><ArrowUpRight size={17} /></a>}
        {selected.attachment && <a className="sp-resource-link" href={selected.attachment.url} target="_blank" rel="noreferrer"><FileText size={20} /><span>{selected.attachment.name}<small>{(selected.attachment.size / 1024).toFixed(0)} KB · Tasdiqlovchi hujjat</small></span><ArrowDownToLine size={17} /></a>}
        {!canModifySelected && <div className="sp-info-box"><ShieldCheck size={18} /><p>Ushbu faoliyat boshqa xodimga tegishli. Siz uni tekshirish uchun ko‘rishingiz mumkin.</p></div>}
        {locked.has(selected.id) && <div className="sp-info-box"><ShieldCheck size={18} /><p>Faoliyat tekshiruvdagi yoki tasdiqlangan hisobotga biriktirilgan. Hujjat yaxlitligini saqlash uchun uni o‘zgartirish cheklangan.</p></div>}
        {detailError && <p className="form-error" role="alert">{detailError}</p>}
        {confirmDelete && <div className="sp-delete-confirm"><p>Bu faoliyatni portfeldan o‘chirasizmi? Amalni ortga qaytarib bo‘lmaydi.</p><button className="btn danger small" disabled={deleting} onClick={deleteActivity}>{deleting ? <LoaderCircle size={15} className="sp-spin" /> : <Trash2 size={15} />} O‘chirishni tasdiqlash</button><button className="btn secondary small" onClick={() => setConfirmDelete(false)}>Bekor qilish</button></div>}
      </div><div className="modal-footer">{canModifySelected && <button className="btn danger" disabled={locked.has(selected.id) || deleting} onClick={() => setConfirmDelete(true)}><Trash2 size={16} />O‘chirish</button>}<button className="btn secondary" onClick={() => setSelected(null)}>Yopish</button>{canModifySelected && <button className="btn primary" disabled={locked.has(selected.id)} onClick={() => { setEditor(selected); setSelected(null); }}><Pencil size={16} />Tahrirlash</button>}</div>
    </SupportingModal>}
  </>;
}

function ActivityEditor({ activity, onClose, onSaved }: { activity: Activity | null; onClose: () => void; onSaved: () => Promise<void> }) {
  const [form, setForm] = useState<ActivityForm>({ title: activity?.title ?? '', category: activity?.category ?? 'article', date: activity?.date ?? localDate(), description: activity?.description ?? '', link: activity?.link ?? '' });
  const [attachment, setAttachment] = useState<Attachment | null>(activity?.attachment ?? null);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const fileRef = useRef<HTMLInputElement>(null);
  const update = (key: keyof ActivityForm, value: string) => setForm(current => ({ ...current, [key]: value }));
  async function save(event: FormEvent) {
    event.preventDefault(); setError('');
    if (file && file.size > 20 * 1024 * 1024) { setError('Fayl hajmi 20 MB dan oshmasligi kerak.'); return; }
    if (form.link.trim() && !/^https?:\/\//i.test(form.link.trim())) { setError('Havola https:// yoki http:// bilan boshlanishi kerak.'); return; }
    setBusy(true);
    try {
      let uploaded = attachment;
      if (file) { const data = new FormData(); data.append('file', file); uploaded = await api<Attachment>('attachments/', { method: 'POST', body: data }); setAttachment(uploaded); setFile(null); }
      const data = { ...form, title: form.title.trim(), description: form.description.trim(), link: form.link.trim(), attachment_id: uploaded?.id ?? null };
      if (activity) await patch(`activities/${activity.id}/`, data); else await post('activities/', data);
      await onSaved();
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Faoliyatni saqlab bo‘lmadi.'); }
    finally { setBusy(false); }
  }
  return <SupportingModal title={activity ? 'Faoliyatni tahrirlash' : 'Yangi faoliyat qo‘shish'} subtitle="Bajargan ishingiz va tasdiqlovchi ma’lumotlarni kiriting." onClose={() => { if (!busy) onClose(); }}>
    <form onSubmit={save}><div className="modal-body sp-form-stack"><label className="field">Faoliyat nomi *<input className="input" required maxLength={240} placeholder="Masalan, sun’iy intellekt bo‘yicha ilmiy maqola" value={form.title} onChange={event => update('title', event.target.value)} /></label><div className="form-grid"><label className="field">Faoliyat turi<select className="input" value={form.category} onChange={event => update('category', event.target.value)}>{categories.map(key => <option key={key} value={key}>{categoryLabels[key]}</option>)}</select></label><label className="field">Sana *<input className="input" type="date" required value={form.date} onChange={event => update('date', event.target.value)} /></label></div>
      <label className="field">Qisqacha tavsif<textarea className="input" rows={3} maxLength={5000} placeholder="Ishning mazmuni, nashr nomi yoki erishilgan natija..." value={form.description} onChange={event => update('description', event.target.value)} /></label>
      <label className="field">Manba havolasi<input className="input" type="url" maxLength={500} placeholder="https://..." value={form.link} onChange={event => update('link', event.target.value)} /><small>DOI, nashr yoki sertifikatni tekshirish havolasi.</small></label>
      <div className="field">Tasdiqlovchi hujjat<input ref={fileRef} className="sp-file-input" type="file" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg,.txt,.xlsx" aria-label="Tasdiqlovchi hujjatni tanlash" onChange={event => { setFile(event.target.files?.[0] ?? null); setError(''); }} /><button type="button" className="sp-upload" onClick={() => fileRef.current?.click()}><UploadCloud size={26} /><strong>{file?.name ?? attachment?.name ?? 'Faylni tanlash uchun bosing'}</strong><span>PDF, Word, rasm yoki Excel · 20 MB gacha</span></button>{(file || attachment) && <button type="button" className="sp-text-button" onClick={() => { setFile(null); setAttachment(null); if (fileRef.current) fileRef.current.value = ''; }}><X size={13} /> Biriktirmani olib tashlash</button>}</div>
      <div className="sp-info-box"><ShieldCheck size={17} /><p>Faoliyat portfelingizga saqlanadi. Uni keyinchalik tegishli hisobotga biriktirishingiz mumkin.</p></div>
      {error && <p className="form-error" role="alert">{error}</p>}
    </div><div className="modal-footer"><button type="button" className="btn secondary" disabled={busy} onClick={onClose}>Bekor qilish</button><button type="submit" className="btn primary" disabled={busy}>{busy ? <LoaderCircle className="sp-spin" size={16} /> : <Check size={16} />}{busy ? 'Saqlanmoqda...' : 'Faoliyatni saqlash'}</button></div></form>
  </SupportingModal>;
}
