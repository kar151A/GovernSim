import {useEffect,useLayoutEffect,useState} from 'react';
export type Theme='light'|'dark';
export const THEME_KEY='governsim.theme.v1';
export function preferredTheme():Theme {
 try {const saved=localStorage.getItem(THEME_KEY);if(saved==='light'||saved==='dark')return saved;}catch{/* Storage can be disabled by browser policy. */}
 return window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';
}
export function applyTheme(theme:Theme) {
 document.documentElement.dataset.theme=theme;
 document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='dark'?'#101b2a':'#111e30');
}
export function useTheme() {
 const [theme,setTheme]=useState<Theme>(preferredTheme);
 useLayoutEffect(()=>{applyTheme(theme);},[theme]);
 useEffect(()=>{
  const media=window.matchMedia('(prefers-color-scheme: dark)');
  function syncSystem(){try{if(localStorage.getItem(THEME_KEY))return;}catch{}setTheme(media.matches?'dark':'light');}
  function syncStorage(event:StorageEvent){if(event.key===THEME_KEY||event.key===null)setTheme(preferredTheme());}
  media.addEventListener('change',syncSystem);window.addEventListener('storage',syncStorage);
  return()=>{media.removeEventListener('change',syncSystem);window.removeEventListener('storage',syncStorage);};
 },[]);
 function toggleTheme() {
  const next=theme==='light'?'dark':'light';
  try{localStorage.setItem(THEME_KEY,next);}catch{/* Appearance still works without persistent storage. */}
  setTheme(next);
 }
 return {theme,toggleTheme};
}
