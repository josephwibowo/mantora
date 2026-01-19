import { Box, Divider, Typography, useTheme } from '@mui/material';
import type { SvgIconComponent } from '@mui/icons-material';
import BuildIcon from '@mui/icons-material/Build';
import StorageIcon from '@mui/icons-material/Storage';
import ViewQuiltIcon from '@mui/icons-material/ViewQuilt';
import BlockIcon from '@mui/icons-material/Block';
import ErrorIcon from '@mui/icons-material/Error';
import WarningIcon from '@mui/icons-material/Warning';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import TableChartIcon from '@mui/icons-material/TableChart';
import type { SessionSummary } from '../api/types';

interface SessionStatsBarProps {
  summary: SessionSummary;
}

interface StatProps {
  icon: SvgIconComponent;
  label: string;
  value: number;
  color?: string;
}

export function SessionStatsBar({ summary }: SessionStatsBarProps) {
  const theme = useTheme();

  const Stat = ({ icon: Icon, label, value, color }: StatProps) => {
    if (value === 0 && (label === 'Errors' || label === 'Blocks' || label === 'Warnings'))
      return null;

    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
          opacity: value === 0 ? 0.6 : 1,
        }}
      >
        <Icon sx={{ fontSize: 14, color: color || 'text.secondary' }} />
        <Typography variant='caption' sx={{ fontWeight: 600, fontFamily: 'monospace' }}>
          {value}
        </Typography>
        <Typography
          variant='caption'
          color='text.secondary'
          sx={{ display: { xs: 'none', md: 'block' }, fontSize: '0.7rem' }}
        >
          {label}
        </Typography>
      </Box>
    );
  };

  const tableCount = summary.tables_touched?.length ?? 0;

  return (
    <Box
      sx={{
        px: 2,
        py: 0.75,
        display: 'flex',
        alignItems: 'center',
        gap: 2,
        borderBottom: 1,
        borderColor: 'divider',
        bgcolor: 'background.paper',
        minHeight: 32,
      }}
    >
      <Stat icon={BuildIcon} label='Tools' value={summary.tool_calls} />
      <Divider orientation='vertical' flexItem sx={{ height: 12, my: 'auto' }} />
      <Stat icon={StorageIcon} label='Queries' value={summary.queries} />
      <Divider orientation='vertical' flexItem sx={{ height: 12, my: 'auto' }} />
      <Stat icon={ViewQuiltIcon} label='Casts' value={summary.casts} />

      {tableCount > 0 && (
        <>
          <Divider orientation='vertical' flexItem sx={{ height: 12, my: 'auto' }} />
          <Stat icon={TableChartIcon} label='Tables' value={tableCount} />
        </>
      )}

      {(summary.blocks > 0 ||
        summary.errors > 0 ||
        summary.warnings > 0 ||
        (summary.approvals ?? 0) > 0) && (
        <Divider orientation='vertical' flexItem sx={{ height: 12, my: 'auto' }} />
      )}

      {summary.approvals !== undefined && summary.approvals > 0 && (
        <Stat
          icon={CheckCircleOutlineIcon}
          label='Approvals'
          value={summary.approvals}
          color={theme.palette.success.main}
        />
      )}

      <Stat
        icon={BlockIcon}
        label='Blocks'
        value={summary.blocks}
        color={theme.palette.warning.main}
      />
      <Stat
        icon={WarningIcon}
        label='Warnings'
        value={summary.warnings}
        color={theme.palette.warning.main}
      />
      <Stat
        icon={ErrorIcon}
        label='Errors'
        value={summary.errors}
        color={theme.palette.error.main}
      />
    </Box>
  );
}
