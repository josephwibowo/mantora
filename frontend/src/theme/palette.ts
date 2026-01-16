import { PaletteMode } from '@mui/material';

export const getPalette = (mode: PaletteMode) => ({
  mode,
  ...(mode === 'dark'
    ? {
        // Dark Mode (GitHub Dark Dimmed / Vercel style)
        background: {
          default: '#0d1117', // Deep gray/black
          paper: '#161b22', // Slightly lighter for cards/panels
        },
        primary: {
          main: '#6366f1', // Indigo
          light: '#818cf8',
          dark: '#4f46e5',
        },
        secondary: {
          main: '#a855f7', // Purple
        },
        text: {
          primary: '#e6edf3',
          secondary: '#8d96a0',
        },
        divider: 'rgba(255, 255, 255, 0.1)',
        action: {
          hover: 'rgba(255, 255, 255, 0.04)',
          selected: 'rgba(255, 255, 255, 0.08)',
        },
      }
    : {
        // Light Mode (Standard clean)
        background: {
          default: '#f6f8fa',
          paper: '#ffffff',
        },
        primary: {
          main: '#6366f1',
        },
        text: {
          primary: '#1f2328',
          secondary: '#656d76',
        },
        divider: 'rgba(0, 0, 0, 0.08)',
      }),
});
