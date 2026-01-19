import { Box, Typography } from '@mui/material';
import { ReactNode } from 'react';

interface RightPanelProps {
  children: ReactNode;
  controls?: ReactNode;
  headerContent?: ReactNode;
}

export function RightPanel({ children, controls, headerContent }: RightPanelProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        bgcolor: 'background.paper',
        borderLeft: 1,
        borderColor: 'divider',
      }}
    >
      <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider' }}>
        {headerContent || (
          <Typography variant='overline' color='text.primary' fontWeight={700}>
            TIMELINE
          </Typography>
        )}
        {controls && <Box sx={{ mt: 1 }}>{controls}</Box>}
      </Box>
      <Box sx={{ flexGrow: 1, overflow: 'auto' }}>{children}</Box>
    </Box>
  );
}
