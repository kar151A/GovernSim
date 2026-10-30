function csrfToken() {
 const value=document.cookie.split('; ').find(c=>c.startsWith('governsim_csrf='));
 return value?decodeURIComponent(value.slice('governsim_csrf='.length)):'';
}
async function failure(response:Response,path:string):Promise<never> {
 if(response.status===401&&(!path.startsWith('/auth/')||path==='/auth/logout'||path==='/auth/password/change'))window.dispatchEvent(new Event('governsim:session-expired'));
 const data=await response.json().catch(()=>({detail:`Request failed (${response.status})`}));
 throw new Error(typeof data.detail==='string'?data.detail:Array.isArray(data.detail)?data.detail.map((e:{msg:string})=>e.msg).join('. '):JSON.stringify(data.detail));
}
export async function api<T>(path:string,body?:unknown):Promise<T> {
 const csrf=csrfToken();
 const response=await fetch(`/api${path}`,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:{...(body===undefined?{}:{'Content-Type':'application/json',...(csrf?{'X-CSRF-Token':csrf}:{})})},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok)return failure(response,path);
 return response.json() as Promise<T>;
}
export async function restoreSession<T>():Promise<T|null> {
 const response=await fetch('/api/session',{credentials:'same-origin'});
 if(response.status===401)return null;
 if(!response.ok)return failure(response,'/auth/session');
 return response.json() as Promise<T>;
}
export async function download(path:string,filename:string) {
 const response=await fetch(`/api${path}`,{credentials:'same-origin'});
 if(!response.ok)return failure(response,path);
 const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
