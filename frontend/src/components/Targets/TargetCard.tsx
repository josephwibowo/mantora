import {
  Check as CheckIcon,
  Circle as CircleIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PowerSettingsNew as PowerIcon,
  Storage as StorageIcon,
} from '@mui/icons-material';
import {
  Box,
  Button,
  Card,
  CardActions,
  CardContent,
  Chip,
  IconButton,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';

import { Target } from '../../api/types';

interface TargetCardProps {
  target: Target;
  isActive: boolean;
  onActivate: (id: string) => void;
  onEdit: (target: Target) => void;
  onDelete: (id: string, name: string) => void;
  isPending?: boolean;
}

export function TargetCard({
  target,
  isActive,
  onActivate,
  onEdit,
  onDelete,
  isPending,
}: TargetCardProps) {
  return (
    <Card
      variant={isActive ? 'elevation' : 'outlined'}
      elevation={isActive ? 3 : 0}
      sx={{
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        borderColor: isActive ? 'success.main' : undefined,
        borderWidth: isActive ? 2 : 1,
        transition: 'all 0.2s',
        '&:hover': {
          borderColor: isActive ? 'success.main' : 'primary.main',
          transform: 'translateY(-2px)',
          boxShadow: isActive ? 6 : 2,
        },
      }}
    >
      <CardContent sx={{ flexGrow: 1, pb: 1 }}>
        <Stack direction='row' justifyContent='space-between' alignItems='flex-start' spacing={2}>
          <Box>
            <Stack direction='row' alignItems='center' spacing={1} mb={1}>
              {isActive ? (
                <CircleIcon color='success' sx={{ fontSize: 12 }} />
              ) : (
                <StorageIcon color='disabled' sx={{ fontSize: 20 }} />
              )}
              <Typography variant='h6' component='div' fontWeight={600}>
                {target.name}
              </Typography>
            </Stack>
            <Chip
              label={target.type}
              size='small'
              variant={isActive ? 'filled' : 'outlined'}
              color={isActive ? 'success' : 'default'}
              sx={{ mb: 2 }}
            />
          </Box>
          {isActive && <Chip label='Active' color='success' size='small' icon={<CheckIcon />} />}
        </Stack>

        <Box
          sx={{
            p: 1.5,
            bgcolor: 'action.hover',
            borderRadius: 1,
            fontFamily: 'monospace',
            fontSize: '0.8rem',
            color: 'text.secondary',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          }}
        >
          $ {target.command.join(' ')}
        </Box>

        {Object.keys(target.env).length > 0 && (
          <Typography variant='caption' color='text.secondary' sx={{ mt: 1, display: 'block' }}>
            {Object.keys(target.env).length} env vars configured
          </Typography>
        )}
      </CardContent>

      <CardActions sx={{ justifyContent: 'space-between', px: 2, pb: 2 }}>
        {isActive ? (
          <Button
            size='small'
            variant='outlined'
            color='inherit'
            startIcon={<CheckIcon />}
            disabled
          >
            Connected
          </Button>
        ) : (
          <Button
            size='small'
            variant='contained'
            startIcon={<PowerIcon />}
            onClick={() => onActivate(target.id)}
            disabled={isPending}
          >
            Connect
          </Button>
        )}

        <Box>
          <Tooltip title='Edit'>
            <IconButton size='small' onClick={() => onEdit(target)}>
              <EditIcon fontSize='small' />
            </IconButton>
          </Tooltip>
          {isActive ? (
            <Tooltip title='Cannot delete active target'>
              <span>
                <IconButton size='small' disabled>
                  <DeleteIcon fontSize='small' />
                </IconButton>
              </span>
            </Tooltip>
          ) : (
            <Tooltip title='Delete'>
              <IconButton
                size='small'
                color='error'
                onClick={() => onDelete(target.id, target.name)}
                disabled={isPending}
              >
                <DeleteIcon fontSize='small' />
              </IconButton>
            </Tooltip>
          )}
        </Box>
      </CardActions>
    </Card>
  );
}
