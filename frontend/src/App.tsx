import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Archive, ArrowRight, Bell, BookOpen, Check, CheckCheck, ChevronDown, ChevronRight, CircleHelp, FileText, GraduationCap, House, LayoutGrid, Layers3, LoaderCircle, LogOut, Menu, Plus, Search, Settings2, KeyRound, ShieldCheck, Sparkles, Target, UserRound, X, CalendarDays } from 'lucide-react';
import { api, ApiError, dateLabel, post } from './api';
import type { Page, Report, ReportType, Workspace } from './types';
import Dashboard from './pages/Dashboard';
import { ReportDetail, ReportEditor, ReportList } from './pages/Reports';
import Templates from './pages/Templates';
import Portfolio from './pages/Portfolio';
import Profile from './pages/Profile';
import WorkPlan from './pages/WorkPlan';
import Modal from './components/Modal';
import PasswordChange from './components/PasswordChange';
import Administration from './pages/Administration';

const pageTitles:Record<Page,{title:string;description:string;breadcrumb:string}>={
  dashboard:{title:'Ish stolim',description:'Faoliyatingiz, natijalaringiz va muhim vazifalar — bir joyda.',breadcrumb:'Ish stoli'},
  portfolio:{title:'Shaxsiy portfel',description:'Har bir ishingiz va yutug‘ingiz — kasbiy yo‘lingizning bir qismi.',breadcrumb:'Shaxsiy portfel'},
  reports:{title:'Hisobotlarim',description:'Portfelingizdan hisobot yarating va tekshiruv jarayonini kuzating.',breadcrumb:'Hisobotlar'},
  plan:{title:'Shaxsiy ish rejam',description:'Aniq maqsadlar, bajarilgan ishlar va oldindagi natijalar.',breadcrumb:'Ish rejam'},
  profile:{title:'Mening profilim',description:'Shaxsiy va kasbiy ma’lumotlaringizni bir joyda boshqaring.',breadcrumb:'Profil'},
  templates:{title:'Tayyor shablonlar',description:'Hisobot tayyorlashni sodda va tushunarli shakldan boshlang.',breadcrumb:'Shablonlar'},
  archive:{title:'Hisobotlar arxivi',description:'Tasdiqlangan hisobotlar va ularning o‘zgarishlar tarixi.',breadcrumb:'Arxiv'},
  review:{title:'Tekshiruv markazi',description:'Xodimlarning hisobotlarini ko‘rib chiqing va aniq fikr bildiring.',breadcrumb:'Tekshiruv'},
  administration:{title:'Universitet boshqaruvi',description:'Xodimlar, tashkiliy tuzilma va amaldagi hisobot shakllari.',breadcrumb:'Boshqaruv'},
};
function getPage():Page {const value=location.hash.slice(1).split('?')[0];return Object.prototype.hasOwnProperty.call(pageTitles,value)?value as Page:'dashboard';}

export default function App() {
  const [workspace,setWorkspace]=useState<Workspace|null>(null);
  const [page,setPage]=useState<Page>(getPage);
  const [loading,setLoading]=useState(true);
  const [loadError,setLoadError]=useState('');
  const [loginNeeded,setLoginNeeded]=useState(false);
  const [message,setMessage]=useState('');
  const [mobileNav,setMobileNav]=useState(false);
  const [isMobile,setIsMobile]=useState(()=>window.matchMedia('(max-width: 800px)').matches);
  const [showNotifications,setShowNotifications]=useState(false);
  const [showAccount,setShowAccount]=useState(false);
  const [help,setHelp]=useState(false);
  const [passwordOpen,setPasswordOpen]=useState(false);
  const [search,setSearch]=useState('');
  const [searchOpen,setSearchOpen]=useState(false);
  const [selectedReport,setSelectedReport]=useState<Report|null>(null);
  const [editing,setEditing]=useState(false);
  const [creating,setCreating]=useState(false);
  const [initialType,setInitialType]=useState<ReportType|undefined>();
  const [initialTemplateId,setInitialTemplateId]=useState<string|undefined>();
  const searchRef=useRef<HTMLInputElement>(null);
  const mobileMenuRef=useRef<HTMLButtonElement>(null);
  const sidebarRef=useRef<HTMLElement>(null);
  const navWasOpen=useRef(false);
  const initialized=useRef(false);
  const toast=useCallback((value:string)=>setMessage(value),[]);
  const refresh=useCallback(async()=>{const data=await api<Workspace>('workspace/');setWorkspace(data);},[]);
  const init=useCallback(async()=>{
    setLoading(true);setLoadError('');setLoginNeeded(false);
    try {
      try {await api('auth/session/');}
      catch(error){
        if (!(error instanceof ApiError)||![401,403].includes(error.status)) throw error;
        setLoginNeeded(true);return;
      }
      await refresh();
    } catch(error) {setLoadError((error as Error).message);}
    finally {setLoading(false);}
  },[refresh]);
  useEffect(()=>{if(initialized.current)return;initialized.current=true;void init();},[init]);
  useEffect(()=>{
    const expire=()=>{setWorkspace(null);setSelectedReport(null);setCreating(false);setEditing(false);setPasswordOpen(false);setHelp(false);setMobileNav(false);setShowAccount(false);setShowNotifications(false);setSearch('');setSearchOpen(false);setLoginNeeded(true);navigate('dashboard');};
    const resume=(event:PageTransitionEvent)=>{if(event.persisted)void init();};
    window.addEventListener('uniflow:session-expired',expire);
    window.addEventListener('pageshow',resume);
    return()=>{window.removeEventListener('uniflow:session-expired',expire);window.removeEventListener('pageshow',resume);};
  },[init]);
  useEffect(()=>{
    const media=window.matchMedia('(max-width: 800px)');
    const resize=()=>{setIsMobile(media.matches);if(!media.matches)setMobileNav(false);};
    media.addEventListener('change',resize);
    return()=>media.removeEventListener('change',resize);
  },[]);
  useLayoutEffect(()=>{
    if(!isMobile||!mobileNav){
      if(navWasOpen.current&&isMobile)mobileMenuRef.current?.focus();
      navWasOpen.current=false;
      return;
    }
    navWasOpen.current=true;
    sidebarRef.current?.querySelector<HTMLButtonElement>('.sidebar-close')?.focus();
    const overflow=document.body.style.overflow;
    document.body.style.overflow='hidden';
    const trapFocus=(event:KeyboardEvent)=>{
      if(event.key!=='Tab')return;
      const controls=sidebarRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]');
      if(!controls?.length)return;
      const first=controls[0],last=controls[controls.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    };
    document.addEventListener('keydown',trapFocus);
    return()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',trapFocus);};
  },[isMobile,mobileNav]);
  useEffect(()=>{const listener=()=>{setPage(getPage());setMobileNav(false);setSearch('');setSearchOpen(false);window.scrollTo({top:0});};window.addEventListener('hashchange',listener);return()=>window.removeEventListener('hashchange',listener);},[]);
  useEffect(()=>{if(!message)return;const timeout=window.setTimeout(()=>setMessage(''),5000);return()=>clearTimeout(timeout);},[message]);
  useEffect(()=>{const listener=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key==='k'){event.preventDefault();searchRef.current?.focus();setSearchOpen(true);}if(event.key==='Escape'){setSearchOpen(false);setShowAccount(false);setShowNotifications(false);setMobileNav(false);}};window.addEventListener('keydown',listener);return()=>window.removeEventListener('keydown',listener);},[]);
  function navigate(target:Page,query='') {location.hash=`${target}${query?`?${query}`:''}`;setPage(target);setMobileNav(false);setShowAccount(false);setSearchOpen(false);}
  async function readNotification(id:number,reportId:number|null) {
    try {await post(`notifications/${id}/read/`,{});await refresh();if(reportId){const report=workspace?.reports.find(r=>r.id===reportId);if(report)setSelectedReport(report);}setShowNotifications(false);}catch(error){toast((error as Error).message);}
  }
  function createReport(type?:ReportType,templateId?:string) {setInitialType(type);setInitialTemplateId(templateId);setCreating(true);}
  if(loading) return <div className="loading-screen"><Brand/><LoaderCircle className="spin" size={26}/><p>Ish maydoningiz tayyorlanmoqda...</p></div>;
  if(loginNeeded) return <Login onSuccess={async()=>{await refresh();setLoginNeeded(false);navigate('dashboard');}}/>;
  if(loadError||!workspace) return <div className="loading-screen"><Brand/><div className="connection-card"><span className="soft-icon large orange"><CircleHelp size={26}/></span><h2>Serverga ulanib bo‘lmadi</h2><p>Backend ishga tushganini tekshiring va qayta urinib ko‘ring.</p><p className="form-error">{loadError}</p><button className="btn primary" onClick={()=>void init()}>Qayta urinish <ArrowRight size={16}/></button></div></div>;
  const {user,profile}=workspace;
  const returned=workspace.reports.filter(r=>r.owner_id===user.id&&r.status==='returned').length;
  const unread=workspace.notifications.filter(n=>!n.read).length;
  const reviewCount=workspace.reports.filter(r=>r.owner_id!==user.id&&r.status==='submitted').length;
  const props={workspace,onRefresh:refresh,toast};
  const navItems:[Page,string,typeof House][]=[['dashboard','Ish stolim',LayoutGrid],['portfolio','Shaxsiy portfel',Layers3],['reports','Hisobotlarim',FileText],['plan','Ish rejam',Target]];
  const management:[Page,string,typeof House][]=[['templates','Shablonlar',BookOpen],['archive','Arxiv',Archive],['profile','Mening profilim',UserRound]];
  if(user.role==='administrator') management.unshift(['administration','Boshqaruv',Settings2]);
  const searchResults=search.trim()?[
    ...workspace.activities.filter(a=>a.owner_id===user.id&&`${a.title} ${a.description}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(a=>({id:`a${a.id}`,title:a.title,type:'Faoliyat',action:()=>navigate('portfolio',`search=${encodeURIComponent(search)}`)})),
    ...workspace.reports.filter(r=>`${r.title} ${r.period}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())).map(r=>({id:`r${r.id}`,title:r.title,type:'Hisobot',action:()=>{setSelectedReport(r);setSearchOpen(false);}}))
  ].slice(0,6):[];
  const liveReport=selectedReport?workspace.reports.find(r=>r.id===selectedReport.id)||selectedReport:null;
  return <div className="app-layout">
    {mobileNav&&<div className="sidebar-backdrop" onClick={()=>setMobileNav(false)}/>}
    <aside id="main-navigation" ref={sidebarRef} className={`sidebar ${mobileNav?'is-open':''}`} inert={isMobile&&!mobileNav} aria-hidden={isMobile&&!mobileNav?true:undefined} role={isMobile&&mobileNav?'dialog':undefined} aria-modal={isMobile&&mobileNav?true:undefined} aria-label={isMobile&&mobileNav?'Asosiy menyu':undefined}><button className="icon-btn sidebar-close" aria-label="Menyuni yopish" onClick={()=>setMobileNav(false)}><X size={18}/></button><a href="#dashboard" className="brand-link" aria-label="UniFlow bosh sahifa"><Brand/></a><div className="workspace-selector"><span className="workspace-icon"><GraduationCap size={21}/></span><div><b>Universitet ish maydoni</b><span>{profile.faculty||'Xodimlar platformasi'}</span></div><ChevronDown size={14}/></div><nav className="sidebar-navigation" aria-label="Asosiy navigatsiya"><div className="nav-group-label">SHAXSIY KABINET</div>{navItems.map(([key,title,Icon])=><button key={key} className={`nav-item ${page===key?'active':''}`} onClick={()=>navigate(key)}><Icon size={19}/><span>{title}</span>{key==='reports'&&returned>0&&<span className="nav-count">{returned}</span>}{key==='dashboard'&&page===key&&<span className="active-dot"/>}</button>)}{['reviewer','administrator'].includes(user.role)&&<button className={`nav-item ${page==='review'?'active':''}`} onClick={()=>navigate('review')}><ShieldCheck size={19}/><span>Tekshiruv markazi</span>{reviewCount>0&&<span className="nav-count">{reviewCount}</span>}</button>}<div className="nav-group-label second">QO‘SHIMCHA</div>{management.map(([key,title,Icon])=><button key={key} className={`nav-item ${page===key?'active':''}`} onClick={()=>navigate(key)}><Icon size={19}/><span>{title}</span>{key==='templates'&&<span className="new-tag">YANGI</span>}</button>)}</nav><div className="sidebar-help"><span className="help-bubble"><CircleHelp size={21}/></span><h4>Yordam kerakmi?</h4><p>Platformadan foydalanish<br/>bo‘yicha qo‘llanma bilan tanishing.</p><button onClick={()=>{setMobileNav(false);setHelp(true);}}>Qo‘llanmani ko‘rish <ArrowUpRightIcon/></button><div className="help-decoration"/></div><button className="sidebar-user" onClick={()=>navigate('profile')}><span className="avatar">{user.initials}</span><span><b>{user.name}</b><small>{profile.position}</small></span><ChevronRight size={16}/></button></aside>
    <div className="main-layout" inert={isMobile&&mobileNav}><header className="topbar"><div className="breadcrumb"><button ref={mobileMenuRef} className="icon-btn mobile-menu" aria-label="Menyuni ochish" aria-controls="main-navigation" aria-expanded={mobileNav} onClick={()=>setMobileNav(true)}><Menu size={21}/></button><House size={16}/><span>/</span><b>{pageTitles[page].breadcrumb}</b></div><div className="topbar-actions"><div className="global-search"><Search size={16}/><input ref={searchRef} aria-label="Platformada qidirish" placeholder="Qidirish..." value={search} onFocus={()=>setSearchOpen(true)} onChange={e=>{setSearch(e.target.value);setSearchOpen(true);}}/><kbd>⌘ K</kbd>{searchOpen&&<div className="search-results"><div className="popover-heading"><b>Tezkor qidiruv</b><button className="icon-btn" onClick={()=>setSearchOpen(false)} aria-label="Qidiruvni yopish"><X size={15}/></button></div>{search.trim()?searchResults.length?searchResults.map(result=><button key={result.id} onClick={result.action}><Search size={16}/><span><b>{result.title}</b><small>{result.type}</small></span><ChevronRight size={15}/></button>):<p className="search-hint">Hech narsa topilmadi.</p>:<p className="search-hint">Faoliyat yoki hisobot nomini yozing.</p>}</div>}</div><div className="popover-anchor"><button className={`icon-btn notification-button ${showNotifications?'selected':''}`} aria-label="Bildirishnomalar" onClick={()=>{setShowNotifications(!showNotifications);setShowAccount(false);}}><Bell size={20}/>{unread>0&&<i/>}</button>{showNotifications&&<div className="notifications-popover"><div className="popover-heading"><h3>Bildirishnomalar</h3><span className="count-pill">{unread} yangi</span></div>{workspace.notifications.length?workspace.notifications.map(notification=><button className={`notification-item ${notification.read?'read':''}`} key={notification.id} onClick={()=>void readNotification(notification.id,notification.report_id)}><span className="soft-icon small violet">{notification.read?<CheckCheck size={16}/>:<Bell size={16}/>}</span><span><b>{notification.title}</b><p>{notification.message}</p><small>{dateLabel(notification.created_at)}</small></span>{!notification.read&&<i className="notification-unread"/>}</button>):<div className="empty-state"><Bell size={24}/><p>Yangi bildirishnoma yo‘q.</p></div>}</div>}</div><span className="topbar-divider"/><div className="popover-anchor"><button className="topbar-user" onClick={()=>{setShowAccount(!showAccount);setShowNotifications(false);}} aria-expanded={showAccount}><span className="avatar small">{user.initials}</span><span><b>{user.name}</b><small>{user.role==='administrator'?'Administrator':user.role==='reviewer'?'Mas’ul tekshiruvchi':'Shaxsiy kabinet'}</small></span><ChevronDown size={14}/></button>{showAccount&&<div className="account-popover"><div className="account-intro"><b>{user.name}</b><small>{user.email}</small></div><button onClick={()=>navigate('profile')}><UserRound size={16}/>Mening profilim</button><button onClick={()=>{setHelp(true);setShowAccount(false);}}><CircleHelp size={16}/>Foydalanish qo‘llanmasi</button><button onClick={()=>{setPasswordOpen(true);setShowAccount(false);}}><KeyRound size={16}/>Parolni o‘zgartirish</button><button onClick={async()=>{try{await post('auth/logout/',{});setShowAccount(false);setShowNotifications(false);setSearch('');setSearchOpen(false);setSelectedReport(null);setEditing(false);setCreating(false);setPasswordOpen(false);setWorkspace(null);setLoginNeeded(true);navigate('dashboard');}catch(error){toast((error as Error).message);}}}><LogOut size={16}/>Chiqish</button></div>}</div></div></header>
      <main className="main-content"><div className="page-heading"><div><div className="eyebrow">{user.role==='administrator'?'UNIVERSITET BOSHQARUVI':user.role==='reviewer'?'MAS’UL XODIM KABINETI':'XODIMNING SHAXSIY KABINETI'}</div><h1>{page==='dashboard'?<>Xayrli kun, {user.name.split(' ')[0]} <span className="greeting-wave">✦</span></>:pageTitles[page].title}</h1><p>{pageTitles[page].description}</p></div>{page==='dashboard'&&<div className="heading-actions"><span className="date-chip"><CalendarDays size={15}/>{dateLabel(new Date().toISOString())}</span><button className="btn primary" onClick={()=>navigate('portfolio','new=1')}><Plus size={17}/>Faoliyat qo‘shish</button></div>}</div>
      {page==='dashboard'&&<Dashboard {...props} navigate={navigate} openReport={setSelectedReport} createReport={()=>createReport()}/>}
      {page==='portfolio'&&<Portfolio {...props}/>}
      {page==='reports'&&<ReportList {...props} onOpen={setSelectedReport} onCreate={()=>createReport()}/>}
      {page==='archive'&&<ReportList {...props} onOpen={setSelectedReport} onCreate={()=>createReport()} archive/>}
      {page==='review'&&(['reviewer','administrator'].includes(user.role)?<ReportList {...props} onOpen={setSelectedReport} onCreate={()=>createReport()} review/>:<div className="empty-state card"><ShieldCheck size={30}/><h3>Bu bo‘lim mas’ul tekshiruvchilar uchun</h3><button className="btn secondary" onClick={()=>navigate('dashboard')}>Ish stoliga qaytish</button></div>)}
      {page==='administration'&&(user.role==='administrator'?<Administration {...props}/>:<div className="empty-state card"><ShieldCheck size={30}/><h3>Administrator vakolati kerak</h3><button className="btn secondary" onClick={()=>navigate('dashboard')}>Ish stoliga qaytish</button></div>)}
      {page==='profile'&&<Profile {...props}/>}
      {page==='plan'&&<WorkPlan {...props}/>}
      {page==='templates'&&<Templates {...props} onUse={createReport}/>}
      <footer className="site-footer"><span>© {new Date().getFullYear()} UniFlow</span><span>Mehnat — natija — rivojlanish.</span><button onClick={()=>setHelp(true)}>Yordam markazi <ArrowRight size={12}/></button></footer></main>
    </div>
    {message&&<div className="toast" role="status"><span><Check size={17}/></span><p>{message}</p><button className="icon-btn" aria-label="Xabarni yopish" onClick={()=>setMessage('')}><X size={16}/></button></div>}
    {(creating||editing&&liveReport)&&<ReportEditor {...props} report={editing&&liveReport?liveReport:undefined} initialType={initialType} initialTemplateId={initialTemplateId} onClose={()=>{setCreating(false);setEditing(false);}} onSaved={report=>{setCreating(false);setEditing(false);setSelectedReport(report);}}/>}
    {liveReport&&!editing&&!creating&&<ReportDetail {...props} report={liveReport} onClose={()=>setSelectedReport(null)} onEdit={()=>setEditing(true)} onUpdate={setSelectedReport}/>}
    {passwordOpen&&<PasswordChange onClose={()=>setPasswordOpen(false)} toast={toast}/>}
    {help&&<Modal title="UniFlow bilan ishlash" subtitle="Kamroq takroriy ish. Ko‘proq aniq natija." onClose={()=>setHelp(false)}><div className="modal-body help-content"><div><span>01</span><section><h3>Profilingizni to‘ldiring</h3><p>Shaxsiy ma’lumotlarni bir marta kiriting. Tashkiliy ma’lumotlarni vakolatli mas’ul boshqaradi.</p></section></div><div><span>02</span><section><h3>Ishlaringizni portfelga qo‘shing</h3><p>Maqola, sertifikat yoki loyihani sana va tasdiqlovchi fayl yoki havola bilan saqlang.</p></section></div><div><span>03</span><section><h3>Hisobot tayyorlang va yuboring</h3><p>Tegishli ishlarni tanlang. Mas’ul izoh bilan qaytarsa, tuzatib qayta yuboring. Tekshiruvdagi ma’lumotlar himoyalanadi.</p></section></div><div><span>04</span><section><h3>Natijani kuzating</h3><p>Tasdiqlangan hisobot arxivga tushadi. Yakuniy nusxani chop etishingiz yoki PDF sifatida saqlashingiz mumkin.</p></section></div><div className="info-strip"><ShieldCheck size={20}/><span>Hisob va vakolatlarni universitet administratori boshqaradi. Hisobotlar tegishli bo‘limning mas’ul xodimi tomonidan tekshiriladi.</span></div></div><footer className="modal-footer"><button className="btn primary" onClick={()=>setHelp(false)}>Tushunarli <Check size={16}/></button></footer></Modal>}
  </div>;
}

function Brand(){return <div className="brand"><span className="brand-mark"><GraduationCap size={25} strokeWidth={1.8}/></span><span>Uni<span>Flow</span><i/></span></div>;}
function ArrowUpRightIcon(){return <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M7 17 17 7M7 7h10v10"/></svg>;}
function Login({onSuccess}:{onSuccess:()=>Promise<void>}){
  const [username,setUsername]=useState('');const [password,setPassword]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  async function login(){setBusy(true);setError('');try{await api('auth/session/').catch(error=>{if(!(error instanceof ApiError)||error.status!==401)throw error;});await post('auth/login/',{username,password});await onSuccess();}catch(failure){setError((failure as Error).message);}finally{setBusy(false);}}
  return <div className="login-screen"><div className="login-art"><Brand/><div><span className="eyebrow">UNIVERSITET XODIMLARI UCHUN</span><h1>Mehnatingiz ko‘rinsin.<br/>Yutuqlaringiz<br/>qadrlansin.</h1><p>Faoliyat, portfel va hisobotlar —<br/>yagona ish maydonida.</p><div className="login-art-icon"><GraduationCap size={100} strokeWidth={1}/><Sparkles size={30}/></div></div><small>UniFlow · Xodimlar platformasi</small></div><div className="login-panel"><div className="login-form"><span className="soft-icon large violet"><GraduationCap size={28}/></span><h1>Xush kelibsiz!</h1><p>Shaxsiy kabinetingizga kiring.</p><form onSubmit={event=>{event.preventDefault();void login();}}><div className="field"><label htmlFor="username">Foydalanuvchi nomi</label><input id="username" maxLength={150} autoFocus className="input" autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required/></div><div className="field"><label htmlFor="password">Parol</label><input id="password" maxLength={128} className="input" type="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} required/></div>{error&&<p className="form-error" role="alert">{error}</p>}<button className="btn primary full-width" disabled={busy}>{busy?'Kirilmoqda...':'Kabinetga kirish'}<ArrowRight size={17}/></button></form></div><p className="login-footer">Kirish uchun hisobni universitet mas’uli taqdim etadi.</p></div></div>;
}
