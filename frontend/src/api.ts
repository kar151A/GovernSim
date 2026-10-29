let token = '';
export function setToken(value:string) {token=value;}
export async function api<T>(path:string, body?:unknown):Promise<T> {
  const response=await fetch(`/api${path}`, {method:body===undefined?'GET':'POST',headers:{Authorization:`Bearer ${token}`,...(body===undefined?{}:{'Content-Type':'application/json'})},body:body===undefined?undefined:JSON.stringify(body)});
  if(!response.ok) {const data=await response.json().catch(()=>({detail:`Request failed (${response.status})`}));throw new Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));}
  return response.json() as Promise<T>;
}
export async function download(path:string, filename:string) {
  const response=await fetch(`/api${path}`,{headers:{Authorization:`Bearer ${token}`}});
  if(!response.ok) throw new Error('Report download failed. Check access and server logs.');
  const blob=await response.blob(), url=URL.createObjectURL(blob), link=document.createElement('a');link.href=url;link.download=filename;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
