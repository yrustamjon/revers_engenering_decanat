import { ArrowRight, ArrowUpRight, BookOpen, Check, ChevronRight, Clock3, FileCheck2, FileText, FlaskConical, GraduationCap, Layers3, Plus, ShieldCheck, Sparkles, Target } from 'lucide-react';
import type { Page, PageProps, Report } from '../types';
import { dateLabel } from '../api';
import Status from '../components/Status';

interface Props extends PageProps { navigate: (page: Page, query?: string) => void; openReport: (report: Report) => void; createReport: () => void }
export default function Dashboard({ workspace, navigate, openReport, createReport }: Props) {
  const { work_items, profile } = workspace;
  const activities = workspace.activities.filter(activity => activity.owner_id === workspace.user.id);
  const reports = workspace.reports.filter(report => report.owner_id === workspace.user.id);
  const approved = reports.filter(report => report.status === 'approved').length;
  const pending = reports.filter(report => report.status === 'submitted').length;
  const returned = reports.filter(report => report.status === 'returned');
  const totalTarget = work_items.reduce((sum,item) => sum + item.target, 0);
  const completed = work_items.reduce((sum,item) => sum + Math.min(item.completed,item.target), 0);
  const progress = totalTarget ? Math.round(completed / totalTarget * 100) : 0;
  const scientific = activities.filter(item => ['article','conference','project'].includes(item.category)).length;
  const recent = [...reports].sort((a,b)=>b.updated_at.localeCompare(a.updated_at)).slice(0,4);
  const months = ['Yan','Fev','Mar','Apr','May','Iyun','Iyul','Avg','Sen','Okt','Noy','Dek'];
  const today = new Date();
  const series = Array.from({length:6}, (_,index) => {
    const date = new Date(today.getFullYear(), today.getMonth()-5+index, 1);
    return { label: months[date.getMonth()], scientific: activities.filter(a => ['article','conference','project'].includes(a.category) && a.date.slice(0,7) === `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}`).length, other: activities.filter(a => !['article','conference','project'].includes(a.category) && a.date.slice(0,7) === `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}`).length };
  });
  const maximum = Math.max(4,...series.map(s=>s.scientific+s.other));
  const profileFields = [profile.full_name,profile.email,profile.phone,profile.department,profile.faculty,profile.position,profile.degree,profile.bio];
  const profileProgress = Math.round(profileFields.filter(Boolean).length/profileFields.length*100);
  return <div className="dashboard-page">
    <section className="welcome-banner">
      <div className="welcome-copy"><span className="banner-eyebrow"><span className="live-dot"/> YANGI IMKONIYATLAR, YANGI NATIJALAR</span><h2>Mehnatingiz ko‘rinsin.<br/>Yutuqlaringiz qadrlansin.</h2><p>Faoliyatingizni jamlang, hisobotlarni oson topshiring<br className="desktop-break"/> va o‘sishingizni kuzatib boring.</p><button className="btn banner-button" onClick={()=>navigate('portfolio')}>Portfelimga o‘tish <ArrowUpRight size={16}/></button></div>
      <div className="banner-art" aria-hidden="true"><div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="art-dots">···<br/>···<br/>···</div><div className="floating-tile tile-check"><Check size={20}/></div><div className="art-document"><div className="document-heading"><div className="document-icon"><GraduationCap size={23}/></div><span>SHAXSIY PORTFEL</span><i/></div><div className="art-line line-long"/><div className="art-line line-medium"/><div className="document-stat"><span className="document-stat-icon"><FlaskConical size={18}/></span><div><b>Ilmiy faoliyat</b><span>Tasdiqlangan natijalar</span></div><Check size={15}/></div><div className="art-line line-long"/><div className="art-line line-short"/><div className="document-footer"><span>Rivojlanish sari bir qadam</span><ArrowUpRight size={14}/></div></div><div className="floating-tile tile-award"><ShieldCheck size={25}/></div><div className="art-spark spark-one">✦</div><div className="art-spark spark-two">✦</div></div>
    </section>

    <div className="stats-grid">
      <Stat icon={<Layers3 size={20}/>} label="Jami faoliyatlar" value={activities.length} tone="violet" detail={<><span className="positive"><ArrowUpRight size={12}/>{activities.filter(a=>a.status==='verified').length}</span> tasdiqlangan natija</>}/>
      <Stat icon={<FlaskConical size={20}/>} label="Ilmiy ishlar" value={scientific} tone="blue" detail="Maqola, konferensiya va loyihalar"/>
      <Stat icon={<FileCheck2 size={20}/>} label="Tasdiqlangan hisobotlar" value={approved} tone="green" detail={<><span className="positive"><Check size={12}/></span> Muvaffaqiyatli qabul qilingan</>}/>
      <Stat icon={<Clock3 size={20}/>} label="Tekshiruvdagi hisobotlar" value={pending} tone="orange" detail={returned.length ? <><span className="attention">{returned.length} ta tuzatish kutilmoqda</span></> : 'Mas’ul xodim ko‘rib chiqmoqda'}/>
    </div>

    <div className="dashboard-middle">
      <section className="card activity-chart-card"><div className="section-heading"><div><h3>Faoliyat dinamikasi</h3><p>Oxirgi 6 oydagi natijalaringiz</p></div><span className="period-select">Oylik <span>⌄</span></span></div><div className="chart-legend"><span><i className="legend-dot violet"/>Ilmiy faoliyat</span><span><i className="legend-dot lavender"/>Boshqa faoliyat</span></div><div className="bar-chart"><div className="chart-y-labels">{[maximum,Math.round(maximum*.75),Math.round(maximum*.5),Math.round(maximum*.25),0].map((n,i)=><span key={i}>{n}</span>)}</div><div className="chart-plot"><div className="chart-grid">{[0,1,2,3,4].map(n=><i key={n}/>)}</div><div className="chart-bars">{series.map((point,index)=><div className="chart-column" key={index}><div className="bar-space"><div className="stacked-bar" style={{height:`${Math.max(2,(point.scientific+point.other)/maximum*100)}%`}} title={`${point.label}: ${point.scientific+point.other} ta faoliyat`}><span className="bar-other" style={{flex:point.other || 0}}/><span className="bar-scientific" style={{flex:point.scientific || 0}}/></div></div><span className={index === 5 ? 'current-month' : ''}>{point.label || months[index]}</span></div>)}</div></div></div><div className="chart-footnote"><span className="chart-foot-icon"><ArrowUpRight size={14}/></span><span>Har bir natija — kasbiy rivojlanish sari qadam.</span></div></section>

      <section className="card plan-summary"><div className="section-heading"><div><h3>Shaxsiy ish rejam</h3><p>Joriy rejaning bajarilishi</p></div><span className="soft-icon violet"><Target size={19}/></span></div><div className="progress-ring" style={{'--progress':`${progress*3.6}deg`} as React.CSSProperties}><div><strong>{progress}<span>%</span></strong><small>bajarildi</small></div></div><div className="plan-totals"><span><i className="legend-dot violet"/>Bajarilgan <b>{completed}</b></span><span><i className="legend-dot pale"/>Qolgan <b>{Math.max(0,totalTarget-completed)}</b></span></div><button className="btn secondary full-width" onClick={()=>navigate('plan')}>Rejani ko‘rish <ArrowRight size={15}/></button></section>
    </div>

    <div className="dashboard-bottom"><section className="card recent-reports"><div className="section-heading"><div><h3>So‘nggi hisobotlar</h3><p>Hisobotlaringiz holatini kuzatib boring</p></div><button className="text-button" onClick={()=>navigate('reports')}>Barchasi <ArrowRight size={15}/></button></div><div className="table-scroll"><table className="data-table"><thead><tr><th>HISOBOT NOMI</th><th>SANA</th><th>HOLATI</th><th aria-label="Ochish"/></tr></thead><tbody>{recent.map(report=><tr key={report.id} onClick={()=>openReport(report)} tabIndex={0} onKeyDown={e=>{if(e.key==='Enter')openReport(report);}}><td><div className={`report-name-icon ${report.status==='returned'?'orange':'violet'}`}><FileText size={17}/></div><div className="table-title"><b>{report.title}</b><span>{report.period}</span></div></td><td className="nowrap">{dateLabel(report.updated_at)}</td><td><Status status={report.status}/></td><td><ChevronRight size={16}/></td></tr>)}</tbody></table>{recent.length===0&&<div className="empty-state"><FileText size={24}/><p>Hozircha hisobotlar yo‘q.</p><button className="btn primary small" onClick={createReport}>Birinchi hisobot</button></div>}</div></section>
      <section className="card quick-actions"><div className="section-heading"><div><h3>Tezkor amallar</h3><p>Kerakli ishga bir qadamda</p></div><Sparkles size={18}/></div><button className="quick-action" onClick={()=>navigate('portfolio','new=1')}><span className="soft-icon violet"><Plus size={20}/></span><span><b>Faoliyat qo‘shish</b><small>Yangi natijangizni saqlang</small></span><ChevronRight size={16}/></button><button className="quick-action" onClick={createReport}><span className="soft-icon blue"><FileText size={20}/></span><span><b>Hisobot tayyorlash</b><small>Portfelingizdan bir necha qadamda</small></span><ChevronRight size={16}/></button><button className="quick-action" onClick={()=>navigate('templates')}><span className="soft-icon green"><BookOpen size={20}/></span><span><b>Tayyor shablonlar</b><small>To‘g‘ri shakldan boshlang</small></span><ChevronRight size={16}/></button><div className="profile-nudge"><div><span className="soft-icon small lavender"><GraduationCap size={16}/></span><b>Profilingiz {profileProgress}% to‘ldirilgan</b></div><div className="thin-progress"><i style={{width:`${profileProgress}%`}}/></div><button className="text-button" onClick={()=>navigate('profile')}>{profileProgress===100?'Profilni ko‘rish':'Profilni to‘ldirish'} <ArrowRight size={13}/></button></div></section>
    </div>
    <div className="dashboard-note"><ShieldCheck size={14}/><span>Ma’lumotlaringiz shaxsiy kabinetingizda saqlanadi.</span></div>
  </div>;
}
function Stat({icon,label,value,tone,detail}:{icon:React.ReactNode;label:string;value:number;tone:string;detail:React.ReactNode}) {
  return <section className="stat-card card"><div className="stat-top"><span>{label}</span><span className={`soft-icon ${tone}`}>{icon}</span></div><strong className="stat-value">{String(value).padStart(2,'0')}</strong><div className="stat-detail">{detail}</div></section>;
}
