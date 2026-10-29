import React from 'react';
import {createRoot} from 'react-dom/client';
import App from './App';
import {applyTheme,preferredTheme} from './useTheme';
import './styles.css';
applyTheme(preferredTheme());
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
