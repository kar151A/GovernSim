import {useRef,useState,type FormEvent} from 'react';
import {ArrowRight,CheckCircle2,KeyRound,Shield} from 'lucide-react';
import {api} from './api';

type Step='login'|'invite'|'setup'|'verify'|'recovery';
interface Setup {secret:string;qr_image:string;expires_in:number}

export function AuthLogin({onAuthenticated,notice=''}:{onAuthenticated:()=>Promise<void>;notice?:string}) {
 const [step,setStep]=useState<Step>('login');
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[invitation,setInvitation]=useState('');
 const [code,setCode]=useState(''),[useRecovery,setUseRecovery]=useState(false),[setup,setSetup]=useState<Setup|null>(null);
 const [recoveryCodes,setRecoveryCodes]=useState<string[]>([]),[saved,setSaved]=useState(false);
 const [error,setError]=useState(''),[busy,setBusy]=useState(false);
 const pending=useRef(false);
 function restart(next:Step){setStep(next);setPassword('');setInvitation('');setCode('');setSetup(null);setRecoveryCodes([]);setSaved(false);setError('');setUseRecovery(false);}
 async function submit(event:FormEvent){
  event.preventDefault();if(pending.current)return;pending.current=true;setBusy(true);setError('');
  try{
   if(step==='login'){await api('/auth/login',{email:email.trim(),password});setPassword('');setCode('');setStep('verify');}
   else if(step==='invite'){const result=await api<Setup>('/auth/enroll/start',{email:email.trim(),password,invitation:invitation.trim()});setPassword('');setInvitation('');setSetup(result);setCode('');setStep('setup');}
   else if(step==='setup'){const result=await api<{recovery_codes:string[]}>('/auth/enroll/confirm',{code:code.trim()});setCode('');setSetup(null);setRecoveryCodes(result.recovery_codes);setStep('recovery');}
   else if(step==='verify'){await api('/auth/verify',{code:code.trim(),recovery:useRecovery});setCode('');await onAuthenticated();}
   else if(step==='recovery'&&saved){setRecoveryCodes([]);await onAuthenticated();}
  }catch(err){setError((err as Error).message);}finally{pending.current=false;setBusy(false);}
 }
 const titles:Record<Step,string>={login:'Sign in to your workspace',invite:'Set up your invited account',setup:'Connect your authenticator',verify:'Verify it’s you',recovery:'Save your recovery codes'};
 return <div className="login-page"><div className="login-art"><div className="brand"><span className="brand-mark"><Shield size={24}/></span>GovernSim<span className="brand-version">CONSOLE</span></div><div><div className="eyebrow light">GOVERNSIM / GOVERNANCE CONSOLE</div><h1>Your AI estate.<br/>One accountable<br/><em>control plane.</em></h1><p>Connect your AI estate, its obligations and its evidence.<br/>Explore the impact before making the change.</p><div className="auth-assurance"><Shield size={17}/><span>Password + authenticator verification</span></div></div><span className="login-foot">DETERMINISTIC DECISIONS. HUMAN ACCOUNTABILITY.</span></div><main className="login-form auth-form"><span className="pill"><KeyRound size={12}/>SECURE WORKSPACE ACCESS</span><h2>{titles[step]}</h2><p className="muted">{step==='login'?'Use your account email and password to continue.':step==='invite'?'Enter the invitation code provided by your workspace administrator.':step==='setup'?'Scan the QR code in an authenticator app, then enter its six-digit code.':step==='verify'?`Enter your ${useRecovery?'recovery code':'authenticator code'} for ${email}.`:'Store these codes somewhere private. Each code can be used once if you lose your authenticator.'}</p>
 {notice&&step==='login'&&<div className="notice">{notice}</div>}
 <form onSubmit={submit} aria-busy={busy}>
 {(step==='login'||step==='invite')&&<><label>Email address<input type="email" name="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} maxLength={254} required autoFocus/></label>{step==='invite'&&<label>Invitation code<input name="invitation" value={invitation} onChange={e=>setInvitation(e.target.value)} minLength={32} maxLength={128} autoComplete="off" required/></label>}<label>{step==='invite'?'Create a password':'Password'}<input type="password" name="password" autoComplete={step==='invite'?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)} minLength={step==='invite'?15:1} maxLength={128} required/></label>{step==='invite'&&<p className="fine-print">Use a unique passphrase of at least 15 characters. Your administrator assigns your role.</p>}</>}
 {step==='setup'&&setup&&<><div className="totp-setup"><img src={setup.qr_image} width={180} height={180} alt="QR code for your GovernSim authenticator setup"/><div><strong>Can’t scan the code?</strong><span>Enter this setup key manually in your authenticator app.</span><code>{setup.secret}</code><small>Keep this key private. Setup expires in 5 minutes.</small></div></div><label>Authenticator code<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} value={code} onChange={e=>setCode(e.target.value)} placeholder="000000" required autoFocus/></label></>}
 {step==='verify'&&<><label>{useRecovery?'Recovery code':'Six-digit code'}<input key={useRecovery?'recovery':'totp'} name="code" inputMode={useRecovery?'text':'numeric'} autoComplete="one-time-code" minLength={useRecovery?16:6} maxLength={useRecovery?32:6} pattern={useRecovery?undefined:'[0-9]{6}'} value={code} onChange={e=>setCode(e.target.value)} placeholder={useRecovery?'xxxx-xxxx-xxxx-xxxx':'000000'} required autoFocus/></label><button className="text-button" type="button" disabled={busy} onClick={()=>{setUseRecovery(v=>!v);setCode('');setError('');}}>{useRecovery?'Use an authenticator code':'Use a recovery code instead'}</button><p className="fine-print">Codes expire quickly. If a code was just accepted, wait for the next one before signing in again.</p></>}
 {step==='recovery'&&<><div className="recovery-grid">{recoveryCodes.map(c=><code key={c}>{c}</code>)}</div><label className="check"><input type="checkbox" checked={saved} onChange={e=>setSaved(e.target.checked)} required/>I have saved my recovery codes in a private place.</label></>}
 {error&&<div className="error" role="alert">{error}</div>}
 <button className="button primary full" disabled={busy||(step==='recovery'&&!saved)}>{busy?'Please wait…':step==='login'?'Continue':step==='invite'?'Set up two-factor verification':step==='setup'?'Verify and finish setup':step==='verify'?'Verify and open workspace':'Open workspace'}<ArrowRight size={17}/></button>
 </form>
 {step==='login'&&<div className="auth-alternate"><span>New to this workspace?</span><button className="text-button" disabled={busy} onClick={()=>restart('invite')}>Set up invited account<ArrowRight size={14}/></button></div>}
 {(step==='invite'||step==='setup'||step==='verify')&&<button className="text-button auth-back" disabled={busy} onClick={()=>restart('login')}>Back to sign in</button>}
 <div className="login-help"><CheckCircle2 size={18}/><p>{step==='invite'||step==='setup'?'An invitation can be used once. If setup expires or is interrupted, ask your administrator to issue a new invitation.':'Your password is checked first. Workspace access is granted after authenticator or recovery-code verification.'}</p></div><p className="fine-print">GovernSim provides decision support for representative controls. It is not legal advice or a compliance certification.</p></main></div>;
}
