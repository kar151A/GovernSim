import {useEffect,useRef,type ReactNode,type KeyboardEvent} from 'react';
import {X,ChevronRight,ArrowUpRight,ShieldCheck,AlertCircle,RefreshCw} from 'lucide-react';
import type {Decision,Graph} from './types';
export function label(text:string) {return text.replaceAll('_',' ').toLowerCase().replace(/\b\w/g,c=>c.toUpperCase()).replace(/\b(?:Ai|Api|Llm|Eu|Uk|Us|Gdpr|Dpdp|Iso|Nist|Rmf|Dpia|Json|Pdf)\b/g,word=>word.toUpperCase());}
export function date(text:string) {return new Date(text).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});}
export function Badge({value}:{value:string}) {return <span className={`badge ${value.toLowerCase()}`}><span className="status-dot"/>{label(value)}</span>;}
export function Empty({title,children}:{title:string;children?:ReactNode}) {return <div className="empty"><ShieldCheck size={28}/><h3>{title}</h3><div className="empty-description">{children}</div></div>;}
export function Modal({title,onClose,children,wide=false}:{title:string;onClose:()=>void;children:ReactNode;wide?:boolean}) {
 const ref=useRef<HTMLDialogElement>(null);
 useEffect(()=>{const dialog=ref.current;dialog?.showModal();return()=>dialog?.close();},[]);
 return <dialog aria-label={title} ref={ref} className={`modal ${wide?'wide':''}`} onCancel={onClose} onClick={e=>{if(e.target===ref.current)onClose();}}><div className="modal-head"><h2>{title}</h2><button className="icon-button" aria-label="Close dialog" onClick={onClose}><X size={19}/></button></div>{children}</dialog>;
}
export function PageHead({eyebrow,title,description,children}:{eyebrow:string;title:string;description:string;children?:ReactNode}) {return <div className="page-head"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{description}</p></div><div className="head-actions">{children}</div></div>;}
export function DecisionTable({decisions,onSelect}:{decisions:Decision[];onSelect:(d:Decision)=>void}) {return <div className="table-scroll"><table><thead><tr><th>Requirement</th><th>Control</th><th>Evidence</th><th>Decision</th><th><span className="sr-only">Details</span></th></tr></thead><tbody>{decisions.map(d=><tr key={`${d.obligation_id}-${d.control_id}`}><td><button className="text-button strong" onClick={()=>onSelect(d)}>{d.title}</button><small>{d.framework.replaceAll('_',' ')} · {d.obligation_id}</small></td><td><span className="mono">{d.control_id}</span><small>{d.control_name}</small></td><td>{d.evidence_ids.length} linked{d.missing_types.length>0&&<small className="warning-text">{d.missing_types.length} type missing</small>}</td><td><Badge value={d.deterministic_status}/></td><td><button className="icon-button" aria-label={`Inspect ${d.title}`} onClick={()=>onSelect(d)}><ChevronRight size={17}/></button></td></tr>)}</tbody></table>{decisions.length===0&&<Empty title="No requirements match this filter"/>}</div>;}
export function Provenance({decision,onClose}:{decision:Decision;onClose:()=>void}) {const p=decision.provenance_links;return <Modal title="Decision provenance" onClose={onClose} wide><div className="modal-body"><div className="split-line"><span className="mono">{decision.obligation_id}</span><Badge value={decision.deterministic_status}/></div><h3>{decision.title}</h3><p className="muted">{decision.reason}</p><div className="notice"><AlertCircle size={17}/><span>{String(p.coverage_note)}</span></div><dl className="detail-grid"><div><dt>Source document</dt><dd>{String(p.source_document)}</dd></div><div><dt>Clause / principle</dt><dd>{String(p.source_clause)}</dd></div><div><dt>Model version</dt><dd>{String(p.model_version)}</dd></div><div><dt>Rule version</dt><dd>{String(p.rule_version)}</dd></div><div><dt>Reviewer</dt><dd>{String(p.reviewer||'No reviewer')}</dd></div><div><dt>Reviewer action</dt><dd>{String(p.reviewer_action)}</dd></div><div><dt>Evidence confidence</dt><dd>{Number(p.confidence).toFixed(2)} · artifact metadata</dd></div><div><dt>Evaluated</dt><dd>{String(p.timestamp)}</dd></div></dl><a className="button secondary" href={String(p.source_url)} target="_blank" rel="noreferrer">Open source <ArrowUpRight size={15}/></a><h4>Evidence artifacts & validity</h4><pre>{JSON.stringify(p.evidence_artifacts,null,2)}</pre><h4>Context fingerprint</h4><code className="break">{decision.context_hash}</code></div></Modal>;}
export function GovernanceGraph({graph}:{graph:Graph}) {
 const groups=['asset','dependency','obligation','control','evidence'];
 const positions=new Map<string,{x:number;y:number}>();
 groups.forEach((kind,col)=>{const nodes=graph.nodes.filter(n=>n.kind===kind);nodes.forEach((n,index)=>positions.set(n.id,{x:20+col*216,y:42+index*58}));});
 const height=Math.max(300,...groups.map(k=>graph.nodes.filter(n=>n.kind===k).length*58+55));
 return <div className="graph-scroll"><svg viewBox={`0 0 1090 ${height}`} style={{minWidth:850,width:'100%',height}} role="img" aria-label="Governance graph connecting the asset, dependencies, obligations, controls and evidence"><title>Governance dependency graph</title>{groups.map((kind,col)=><text key={kind} x={20+col*216} y={19} className="graph-heading">{label(kind)}</text>)}{graph.edges.map((e,i)=>{const a=positions.get(e.source),b=positions.get(e.target);if(!a||!b)return null;return <path key={i} d={`M ${a.x+184} ${a.y+18} C ${a.x+208} ${a.y+18}, ${b.x-24} ${b.y+18}, ${b.x} ${b.y+18}`} className="graph-edge"/>;})}{graph.nodes.map(n=>{const p=positions.get(n.id);return p?<g key={n.id}><title>{n.label} · {n.status||n.kind}</title><rect x={p.x} y={p.y} width={184} height={37} rx={6} className={`graph-node ${n.kind} ${n.status==='EVIDENCE_GAP'?'gap':''}`}/><text x={p.x+10} y={p.y+23} className="graph-label">{n.label.length>24?n.label.slice(0,23)+'…':n.label}</text></g>:null;})}</svg></div>;
}

export function WorkspaceLoading() {
 return <div className="workspace-loading" role="status" aria-label="Loading governance workspace"><div className="loading-heading"><RefreshCw size={18}/><span>Loading governance workspace…</span></div><div className="skeleton skeleton-title"/><div className="skeleton skeleton-hero"/><div className="loading-stats">{[0,1,2,3].map(i=><div className="skeleton" key={i}/>)}</div><div className="skeleton skeleton-table"/></div>;
}

export function Tabs({id,label:accessibleLabel,items,value,onChange}:{id:string;label:string;items:{name:string;count?:number}[];value:string;onChange:(value:string)=>void}) {
 function keyboard(event:KeyboardEvent<HTMLButtonElement>,index:number) {
  let next=index;
  if(event.key==='ArrowRight')next=(index+1)%items.length;
  else if(event.key==='ArrowLeft')next=(index-1+items.length)%items.length;
  else if(event.key==='Home')next=0;
  else if(event.key==='End')next=items.length-1;
  else return;
  event.preventDefault();onChange(items[next].name);
  document.getElementById(`${id}-tab-${items[next].name}`)?.focus();
 }
 return <div className="tabs" role="tablist" aria-label={accessibleLabel}>{items.map((item,index)=><button key={item.name} id={`${id}-tab-${item.name}`} role="tab" aria-selected={value===item.name} aria-controls={`${id}-panel`} tabIndex={value===item.name?0:-1} className={value===item.name?'active':''} onClick={()=>onChange(item.name)} onKeyDown={e=>keyboard(e,index)}>{item.name}{item.count!==undefined&&<span className="count">{item.count}</span>}</button>)}</div>;
}
