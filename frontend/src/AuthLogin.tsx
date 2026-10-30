import {useEffect,useRef,useState,type FormEvent} from 'react';
import {ArrowRight,CheckCircle2,KeyRound,Mail,Shield} from 'lucide-react';
import {api} from './api';

type Step='login'|'signup'|'signup-code'|'forgot'|'reset'|'setup'|'verify'|'recovery';
interface Setup {secret:string;qr_image:string;expires_in:number}
interface EmailResult {message:string;expires_in:number;resend_after:number}

export function AuthLogin({onAuthenticated,notice=''}:{onAuthenticated:()=>Promise<void>;notice?:string}) {
 const [step,setStep]=useState<Step>('login');
 const [email,setEmail]=useState(''),[password,setPassword]=useState(''),[confirmation,setConfirmation]=useState('');
 const [code,setCode]=useState(''),[useRecovery,setUseRecovery]=useState(false),[setup,setSetup]=useState<Setup|null>(null);
 const [recoveryCodes,setRecoveryCodes]=useState<string[]>([]),[saved,setSaved]=useState(false);
 const [error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false),[resendSeconds,setResendSeconds]=useState(0);
 const pending=useRef(false);
 useEffect(()=>{if(resendSeconds<=0)return;const timer=setTimeout(()=>setResendSeconds(s=>Math.max(0,s-1)),1000);return()=>clearTimeout(timer);},[resendSeconds]);
 function restart(next:Step){setStep(next);setPassword('');setConfirmation('');setCode('');setSetup(null);setRecoveryCodes([]);setSaved(false);setError('');setMessage('');setUseRecovery(false);setResendSeconds(0);}
 async function sendEmail(purpose:'signup'|'reset') {
  const result=await api<EmailResult>('/auth/email/request',{email:email.trim(),purpose});
  setMessage(result.message);setResendSeconds(result.resend_after);setCode('');
  setStep(purpose==='signup'?'signup-code':'reset');
 }
 async function resend(){
  if(pending.current||resendSeconds>0)return;pending.current=true;setBusy(true);setError('');
  try{await sendEmail(step==='signup-code'?'signup':'reset');}catch(err){setError((err as Error).message);}finally{pending.current=false;setBusy(false);}
 }
 async function submit(event:FormEvent){
  event.preventDefault();if(pending.current)return;pending.current=true;setBusy(true);setError('');
  try{
   if((step==='signup-code'||step==='reset')&&password!==confirmation)throw new Error('Passwords do not match. Enter the same password in both fields.');
   if(step==='login'){await api('/auth/login',{email:email.trim(),password});setPassword('');setCode('');setMessage('');setStep('verify');}
   else if(step==='signup'||step==='forgot')await sendEmail(step==='signup'?'signup':'reset');
   else if(step==='signup-code'){
    const result=await api<Setup>('/auth/email/enroll',{code:code.trim(),password,password_confirm:confirmation});
    setPassword('');setConfirmation('');setCode('');setMessage('');setSetup(result);setStep('setup');
   }
   else if(step==='reset'){
    await api('/auth/password/reset',{code:code.trim(),password,password_confirm:confirmation});
    restart('login');setMessage('Password reset successfully. Sign in with your new password and your authenticator or recovery code.');
   }
   else if(step==='setup'){
    const result=await api<{recovery_codes:string[]}>('/auth/enroll/confirm',{code:code.trim()});
    setCode('');setSetup(null);setRecoveryCodes(result.recovery_codes);setStep('recovery');
   }
   else if(step==='verify'){await api('/auth/verify',{code:code.trim(),recovery:useRecovery});setCode('');await onAuthenticated();}
   else if(step==='recovery'&&saved){await onAuthenticated();setRecoveryCodes([]);}
  }catch(err){setError((err as Error).message);}finally{pending.current=false;setBusy(false);}
 }
 const titles:Record<Step,string>={login:'Sign in to your workspace',signup:'Verify your account email','signup-code':'Create your password',forgot:'Forgot your password?',reset:'Reset your password',setup:'Connect your authenticator',verify:'Verify it’s you',recovery:'Save your recovery codes'};
 const descriptions:Record<Step,string>={
  login:'Use your account email and password to continue.',
  signup:'Enter your administrator-approved email. We will send you a verification code.',
  'signup-code':`Enter the email code for ${email}, then choose and confirm your password.`,
  forgot:'Enter your account email to request a password reset code.',
  reset:`Enter the reset code sent to ${email}, then choose and confirm a new password.`,
  setup:'Scan the QR code in an authenticator app, then enter its six-digit code.',
  verify:`Enter your ${useRecovery?'recovery code':'authenticator code'} for ${email}.`,
  recovery:'Store these codes somewhere private. Each code can be used once if you lose your authenticator.'
 };
 const emailEntry=step==='login'||step==='signup'||step==='forgot';
 const emailCode=step==='signup-code'||step==='reset';
 const labels:Record<Step,string>={login:'Continue',signup:'Send verification code','signup-code':'Verify email and create password',forgot:'Send password reset code',reset:'Reset password',setup:'Verify and finish setup',verify:'Verify and open workspace',recovery:'Open workspace'};
 return <div className="login-page">
  <div className="login-art"><div className="brand"><span className="brand-mark"><Shield size={24}/></span>GovernSim<span className="brand-version">CONSOLE</span></div><div><div className="eyebrow light">GOVERNSIM / GOVERNANCE CONSOLE</div><h1>Your AI estate.<br/>One accountable<br/><em>control plane.</em></h1><p>Connect your AI estate, its obligations and its evidence.<br/>Explore the impact before making the change.</p><div className="auth-assurance"><Shield size={17}/><span>Verified email. Protected account. Two-factor access.</span></div></div><span className="login-foot">DETERMINISTIC DECISIONS. HUMAN ACCOUNTABILITY.</span></div>
  <main className="login-form auth-form"><span className="pill"><KeyRound size={12}/>SECURE WORKSPACE ACCESS</span><h2>{titles[step]}</h2><p className="muted auth-description">{descriptions[step]}</p>
   {notice&&step==='login'&&<div className="notice">{notice}</div>}
   {message&&<div className="auth-message" role="status"><Mail size={16}/><span>{message}</span></div>}
   <form onSubmit={submit} aria-busy={busy}>
    {emailEntry&&<label>Email address<input type="email" name="email" autoComplete="username" value={email} onChange={e=>setEmail(e.target.value)} maxLength={254} required autoFocus/></label>}
    {step==='login'&&<><label>Password<input type="password" name="password" autoComplete="current-password" value={password} onChange={e=>setPassword(e.target.value)} minLength={1} maxLength={128} required/></label><button className="text-button auth-forgot" type="button" disabled={busy} onClick={()=>restart('forgot')}>Forgot password?</button></>}
    {emailCode&&<>
     <label>Email verification code<input name="email-code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} value={code} onChange={e=>setCode(e.target.value)} placeholder="000000" required autoFocus/></label>
     <p className="fine-print">The email code expires in 5 minutes. Use the browser where you requested it.</p>
     <label>{step==='reset'?'New password':'Create a password'}<input type="password" name="new-password" autoComplete="new-password" value={password} onChange={e=>setPassword(e.target.value)} minLength={15} maxLength={128} required/></label>
     <label>Re-enter password<input type="password" name="confirm-password" autoComplete="new-password" value={confirmation} onChange={e=>setConfirmation(e.target.value)} minLength={15} maxLength={128} required/></label>
     <p className="fine-print">Use a unique passphrase of at least 15 characters.</p>
    </>}
    {step==='setup'&&setup&&<><div className="totp-setup"><img src={setup.qr_image} width={180} height={180} alt="QR code for your GovernSim authenticator setup"/><div><strong>Can’t scan the code?</strong><span>Enter this setup key manually in your authenticator app.</span><code>{setup.secret}</code><small>Keep this key private. Setup expires in 5 minutes.</small></div></div><label>Authenticator code<input name="code" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" minLength={6} maxLength={6} value={code} onChange={e=>setCode(e.target.value)} placeholder="000000" required autoFocus/></label></>}
    {step==='verify'&&<><label>{useRecovery?'Recovery code':'Six-digit code'}<input key={useRecovery?'recovery':'totp'} name="code" inputMode={useRecovery?'text':'numeric'} autoComplete="one-time-code" minLength={useRecovery?16:6} maxLength={useRecovery?32:6} pattern={useRecovery?undefined:'[0-9]{6}'} value={code} onChange={e=>setCode(e.target.value)} placeholder={useRecovery?'xxxx-xxxx-xxxx-xxxx':'000000'} required autoFocus/></label><button className="text-button" type="button" disabled={busy} onClick={()=>{setUseRecovery(v=>!v);setCode('');setError('');}}>{useRecovery?'Use an authenticator code':'Use a recovery code instead'}</button><p className="fine-print">Codes expire quickly. If a code was just accepted, wait for the next one before signing in again.</p></>}
    {step==='recovery'&&<><div className="recovery-grid">{recoveryCodes.map(c=><code key={c}>{c}</code>)}</div><label className="check"><input type="checkbox" checked={saved} onChange={e=>setSaved(e.target.checked)} required/>I have saved my recovery codes in a private place.</label></>}
    {error&&<div className="error" role="alert">{error}</div>}
    <button className="button primary full" disabled={busy||(step==='recovery'&&!saved)}>{busy?'Please wait…':labels[step]}<ArrowRight size={17}/></button>
   </form>
   {emailCode&&<div className="auth-resend"><button className="text-button" type="button" disabled={busy||resendSeconds>0} onClick={()=>{void resend();}}>{resendSeconds>0?`Resend code in ${resendSeconds}s`:'Resend email code'}</button><button className="text-button" disabled={busy} onClick={()=>restart(step==='signup-code'?'signup':'forgot')}>Use a different email</button></div>}
   {step==='login'&&<div className="auth-alternate"><span>First time here?</span><button className="text-button" disabled={busy} onClick={()=>restart('signup')}>Set up your account<ArrowRight size={14}/></button></div>}
   {step!=='login'&&step!=='recovery'&&<button className="text-button auth-back" disabled={busy} onClick={()=>restart('login')}>Back to sign in</button>}
   <div className="login-help"><CheckCircle2 size={18}/><p>{step==='signup'||step==='signup-code'?'Your administrator approves account access and assigns your role. Verification codes arrive only by email.':step==='forgot'||step==='reset'?'Resetting your password signs out all sessions. Your authenticator and recovery codes remain required for sign-in.':'Workspace access requires your password and an authenticator or recovery code.'}</p></div><p className="fine-print">GovernSim provides decision support for representative controls. It is not legal advice or a compliance certification.</p>
  </main>
 </div>;
}
