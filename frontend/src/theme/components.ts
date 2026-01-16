import { Theme } from '@mui/material/styles';

export const getComponents = (theme: Theme) => ({
  MuiCssBaseline: {
    styleOverrides: {
      body: {
        scrollbarWidth: 'thin',
        '&::-webkit-scrollbar': {
          width: '8px',
          height: '8px',
        },
        '&::-webkit-scrollbar-track': {
          background: theme.palette.mode === 'dark' ? '#0d1117' : '#f1f1f1',
        },
        '&::-webkit-scrollbar-thumb': {
          backgroundColor: theme.palette.mode === 'dark' ? '#30363d' : '#888',
          borderRadius: '4px',
        },
        '&::-webkit-scrollbar-thumb:hover': {
          backgroundColor: theme.palette.mode === 'dark' ? '#484f58' : '#555',
        },
      },
    },
  },
  MuiButton: {
    styleOverrides: {
      root: {
        borderRadius: 6,
      },
    },
  },
  MuiPaper: {
    styleOverrides: {
      root: {
        backgroundImage: 'none', // Remove elevation overlay in dark mode
        border: `1px solid ${theme.palette.divider}`,
      },
      elevation0: {
        border: 'none',
      },
    },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        borderRadius: 6,
        height: 24,
        fontSize: '0.75rem',
      },
    },
  },
  MuiListItem: {
    styleOverrides: {
      root: {
        paddingTop: 4,
        paddingBottom: 4,
      },
      dense: {
        paddingTop: 2,
        paddingBottom: 2,
      },
    },
  },
  MuiListItemText: {
    styleOverrides: {
      primary: {
        fontSize: '0.8125rem',
      },
      secondary: {
        fontSize: '0.75rem',
      },
    },
  },
});
