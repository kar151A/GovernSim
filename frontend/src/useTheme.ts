import {useLayoutEffect,useState} from 'react';
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
 function toggleTheme() {
  const next=theme==='light'?'dark':'light';
  try{localStorage.setItem(THEME_KEY,next);}catch{/* Appearance still works without persistent storage. */}
  setTheme(next);
 }
 return {theme,toggleTheme};
}
