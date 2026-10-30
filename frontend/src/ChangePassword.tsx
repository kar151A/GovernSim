import {useRef,useState,type FormEvent} from 'react';
import {KeyRound} from 'lucide-react';
import {api} from './api';
import {Modal} from './ui';

export function ChangePassword({onClose,onChanged}:{onClose:()=>void;onChanged:()=>void}) {
 const [current,setCurrent]=useState(''),[password,setPassword]=useState(''),[confirmation,setConfirmation]=useState('');
 const [busy,setBusy]=useState(false),[error,setError]=useState('');
 const pending=useRef(false);
 async function submit(event:FormEvent){
  event.preventDefault();if(pending.current)return;
  if(password!==confirmation){setError('Passwords do not match. Enter the same password in both fields.');return;}
  pending.current=true;setBusy(true);setError('');
  try{await api('/auth/password/change',{current_password:current,password,password_confirm:confirmation});setCurrent('');setPassword('');setConfirmation('');onChanged();}
  catch(err){setError((err as Error).message);}finally{pending.current=false;setBusy(false);}
 }
 return <Modal title="Change password" onClose={()=>{if(!pending.current)onClose();}}><form className="modal-body form-grid" onSubmit={submit} aria-busy={busy}>
  <p className="muted span-2">Choose a unique passphrase of at least 15 characters. Changing your password signs out every session.</p>
  <label className="span-2">Current password<input type="password" name="current-password" autoComplete="current-password" value={current} onChange={e=>setCurrent(e.target.value)} maxLength={128} required autoFocus/></label>
  <label className="span-2">New password<input type="password" name="new-password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} minLength={15} maxLength={128} required/></label>
  <label className="span-2">Re-enter password<input type="password" name="confirm-password" autoComplete="new-password" value={confirmation} onChange={e=>setConfirmation(e.target.value)} minLength={15} maxLength={128} required/></label>
  {error&&<div className="error span-2" role="alert">{error}</div>}
  <div className="form-actions span-2"><button className="button secondary" type="button" disabled={busy} onClick={onClose}>Cancel</button><button className="button primary" disabled={busy}>{busy?'Changing…':'Change password'}<KeyRound size={16}/></button></div>
 </form></Modal>;
}
