import { useState } from 'react';
import { Check, KeyRound, ShieldCheck } from 'lucide-react';
import { post } from '../api';
import Modal from './Modal';
export default function PasswordChange({onClose,toast}:{onClose:()=>void;toast:(message:string)=>void}) {
  const [current,setCurrent]=useState('');const [password,setPassword]=useState('');const [confirmation,setConfirmation]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
  async function save(event:React.FormEvent) {
    event.preventDefault();setError('');
    if(password!==confirmation){setError('Yangi parol va uning takrori mos kelmadi.');return;}
    setBusy(true);
    try {await post('auth/password/',{current_password:current,new_password:password});toast('Parolingiz yangilandi.');onClose();}catch(failure){setError((failure as Error).message);}finally{setBusy(false);}
  }
  return <Modal title="Parolni o‘zgartirish" subtitle="Hisobingiz uchun kuchli va alohida paroldan foydalaning." onClose={()=>{if(!busy)onClose();}}><form onSubmit={save}><div className="modal-body"><div className="field"><label htmlFor="current-password">Amaldagi parol</label><input className="input" id="current-password" type="password" autoComplete="current-password" required value={current} onChange={event=>setCurrent(event.target.value)}/></div><div className="field"><label htmlFor="new-password">Yangi parol</label><input className="input" id="new-password" type="password" autoComplete="new-password" required minLength={8} value={password} onChange={event=>setPassword(event.target.value)}/></div><div className="field"><label htmlFor="confirm-password">Yangi parolni takrorlang</label><input className="input" id="confirm-password" type="password" autoComplete="new-password" required minLength={8} value={confirmation} onChange={event=>setConfirmation(event.target.value)}/></div><div className="info-strip"><ShieldCheck size={18}/><span>Kamida 8 belgi. Ismingizga o‘xshash, juda oddiy yoki faqat raqamlardan iborat parol qabul qilinmaydi.</span></div>{error&&<p className="form-error" role="alert">{error}</p>}</div><div className="modal-footer"><button type="button" className="btn secondary" onClick={onClose} disabled={busy}>Bekor qilish</button><button className="btn primary" disabled={busy}>{busy?<KeyRound size={16}/>:<Check size={16}/>} {busy?'Yangilanmoqda...':'Parolni yangilash'}</button></div></form></Modal>;
}
