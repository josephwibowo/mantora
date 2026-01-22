import {
  Check as CheckIcon,
  Circle as CircleIcon,
  ExpandMore as ExpandMoreIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import {
  Box,
  Button,
  Divider,
  ListItemIcon,
  ListItemText,
  Menu,
  MenuItem,
  Typography,
} from '@mui/material';
import { useEffect, useState } from 'react';

import { useActivateTarget, useActiveTarget, useTargets } from '../../api/queries';
import { Target } from '../../api/types';
import { TargetsManagerDialog } from '../Targets/TargetsManagerDialog';

export function TargetSwitcher() {
  const { data: targets = [] } = useTargets();
  const { data: activeTarget, isLoading: isActiveLoading } = useActiveTarget();
  const activateMutation = useActivateTarget();

  // Auto-activate single target
  useEffect(() => {
    if (!isActiveLoading && targets.length === 1 && !activeTarget && !activateMutation.isPending) {
      activateMutation.mutate(targets[0].id);
    }
  }, [targets, activeTarget, isActiveLoading, activateMutation]);

  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const [isManagerOpen, setIsManagerOpen] = useState(false);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleActivate = async (target: Target) => {
    await activateMutation.mutateAsync(target.id);
    handleClose();
  };

  return (
    <>
      <Button
        onClick={handleClick}
        size='small'
        variant='outlined'
        color={activeTarget ? 'success' : 'inherit'}
        startIcon={
          activeTarget ? (
            <CircleIcon sx={{ fontSize: 12, color: 'success.main' }} />
          ) : (
            <CircleIcon sx={{ fontSize: 12, color: 'text.disabled' }} />
          )
        }
        endIcon={<ExpandMoreIcon fontSize='small' />}
        sx={{
          textTransform: 'none',
          borderRadius: 10,
          borderColor: activeTarget ? 'success.light' : 'divider',
          color: activeTarget ? 'success.main' : 'text.secondary',
          fontWeight: 600,
          mr: 1,
          backgroundColor: activeTarget ? 'success.50' : 'transparent',
          '&:hover': {
            backgroundColor: activeTarget ? 'success.100' : 'action.hover',
            borderColor: activeTarget ? 'success.main' : 'text.primary',
          },
        }}
      >
        {activeTarget ? activeTarget.name : 'Select Target'}
      </Button>

      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        PaperProps={{
          elevation: 2,
          sx: { width: 220, mt: 1, borderRadius: 2 },
        }}
        transformOrigin={{ horizontal: 'right', vertical: 'top' }}
        anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
      >
        <Box sx={{ px: 2, py: 1 }}>
          <Typography variant='caption' color='text.secondary' fontWeight={700}>
            SWITCH TARGET
          </Typography>
        </Box>

        {targets.length === 0 ? (
          <MenuItem disabled>
            <Typography variant='body2' color='text.secondary'>
              No targets configured
            </Typography>
          </MenuItem>
        ) : (
          targets.map((target) => (
            <MenuItem
              key={target.id}
              onClick={() => handleActivate(target)}
              selected={activeTarget?.id === target.id}
            >
              <ListItemIcon>
                {activeTarget?.id === target.id ? (
                  <CheckIcon fontSize='small' color='success' />
                ) : (
                  <StorageIcon fontSize='small' />
                )}
              </ListItemIcon>
              <ListItemText primary={target.name} secondary={target.type} />
            </MenuItem>
          ))
        )}

        <Divider sx={{ my: 1 }} />

        <MenuItem
          onClick={() => {
            handleClose();
            setIsManagerOpen(true);
          }}
        >
          <ListItemIcon>
            <StorageIcon fontSize='small' />
          </ListItemIcon>
          <ListItemText primary='Manage Targets' />
        </MenuItem>
      </Menu>

      <TargetsManagerDialog open={isManagerOpen} onClose={() => setIsManagerOpen(false)} />
    </>
  );
}
