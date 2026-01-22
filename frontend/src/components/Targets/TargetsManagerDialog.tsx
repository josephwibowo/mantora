import { Add as AddIcon, ArrowBack as ArrowBackIcon } from '@mui/icons-material';
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Grid,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { ChangeEvent, FormEvent, useState } from 'react';

import {
  useActivateTarget,
  useCreateTarget,
  useDeleteTarget,
  useTargets,
  useUpdateTarget,
} from '../../api/queries';
import { Target } from '../../api/types';
import { TargetCard } from './TargetCard';

interface TargetsManagerDialogProps {
  open: boolean;
  onClose: () => void;
}

interface FormValues {
  name: string;
  type: string;
  command: string;
  env: string;
}

interface FormErrors {
  name?: string;
  type?: string;
  command?: string;
  env?: string;
}

const INITIAL_VALUES: FormValues = {
  name: '',
  type: 'duckdb',
  command: '',
  env: '{}',
};

export function TargetsManagerDialog({ open, onClose }: TargetsManagerDialogProps) {
  const { data: targets = [] } = useTargets();
  const createMutation = useCreateTarget();
  const updateMutation = useUpdateTarget();
  const deleteMutation = useDeleteTarget();
  const activateMutation = useActivateTarget();

  const [view, setView] = useState<'list' | 'form'>('list');
  const [editingTarget, setEditingTarget] = useState<Target | null>(null);
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [errors, setErrors] = useState<FormErrors>({});

  const validate = (vals: FormValues): FormErrors => {
    const newErrors: FormErrors = {};
    if (!vals.name.trim()) newErrors.name = 'Name is required';
    if (!vals.type) newErrors.type = 'Type is required';
    if (!vals.command.trim()) newErrors.command = 'Command is required';

    if (vals.env) {
      try {
        JSON.parse(vals.env);
      } catch {
        newErrors.env = 'Must be valid JSON';
      }
    }
    return newErrors;
  };

  const handleSwitchToForm = (target?: Target) => {
    if (target) {
      setEditingTarget(target);
      setValues({
        name: target.name,
        type: target.type,
        command: target.command.join(' '),
        env: JSON.stringify(target.env, null, 2),
      });
    } else {
      setEditingTarget(null);
      setValues(INITIAL_VALUES);
    }
    setErrors({});
    setView('form');
  };

  const handleSwitchToList = () => {
    setView('list');
    setEditingTarget(null);
    setValues(INITIAL_VALUES);
    setErrors({});
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setValues((prev) => ({ ...prev, [name]: value }));
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();

    const newErrors = validate(values);
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    const command = values.command.trim().split(/\s+/);
    const env = JSON.parse(values.env || '{}');

    try {
      if (editingTarget) {
        await updateMutation.mutateAsync({
          id: editingTarget.id,
          data: {
            name: values.name,
            type: values.type,
            command,
            env,
          },
        });
      } else {
        await createMutation.mutateAsync({
          name: values.name,
          type: values.type,
          command,
          env,
        });
      }
      handleSwitchToList();
    } catch (error) {
      console.error('Failed to save target:', error);
    }
  };

  const handleDelete = async (id: string, name: string) => {
    if (window.confirm(`Are you sure you want to delete target "${name}"?`)) {
      await deleteMutation.mutateAsync(id);
    }
  };

  const handleActivate = async (id: string) => {
    await activateMutation.mutateAsync(id);
  };

  const activeTarget = targets.find((t) => t.is_active);
  const availableTargets = targets.filter((t) => !t.is_active);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth='md'
      fullWidth
      PaperProps={{ sx: { minHeight: 400, maxHeight: '80vh' } }}
    >
      {view === 'list' && (
        <>
          <DialogTitle
            sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
          >
            Manage Targets
            <Button
              variant='contained'
              size='small'
              startIcon={<AddIcon />}
              onClick={() => handleSwitchToForm()}
            >
              Add Target
            </Button>
          </DialogTitle>
          <DialogContent dividers>
            {targets.length === 0 ? (
              <Stack alignItems='center' spacing={2} sx={{ py: 8, color: 'text.secondary' }}>
                <Typography variant='body1'>No targets configured</Typography>
                <Button
                  variant='outlined'
                  startIcon={<AddIcon />}
                  onClick={() => handleSwitchToForm()}
                >
                  Create First Target
                </Button>
              </Stack>
            ) : (
              <Stack spacing={4} sx={{ pt: 1 }}>
                {activeTarget && (
                  <Stack spacing={1}>
                    <Typography variant='subtitle2' color='success.main' fontWeight={600}>
                      ACTIVE
                    </Typography>
                    <TargetCard
                      target={activeTarget}
                      isActive={true}
                      onActivate={handleActivate}
                      onEdit={handleSwitchToForm}
                      onDelete={handleDelete}
                      isPending={activateMutation.isPending}
                    />
                  </Stack>
                )}

                {availableTargets.length > 0 && (
                  <Stack spacing={1}>
                    <Typography variant='subtitle2' color='text.secondary' fontWeight={600}>
                      AVAILABLE
                    </Typography>
                    <Grid container spacing={2}>
                      {availableTargets.map((target) => (
                        <Grid item xs={12} sm={6} key={target.id}>
                          <TargetCard
                            target={target}
                            isActive={false}
                            onActivate={handleActivate}
                            onEdit={handleSwitchToForm}
                            onDelete={handleDelete}
                            isPending={activateMutation.isPending}
                          />
                        </Grid>
                      ))}
                    </Grid>
                  </Stack>
                )}
              </Stack>
            )}
          </DialogContent>
          <DialogActions>
            <Button onClick={onClose}>Close</Button>
          </DialogActions>
        </>
      )}

      {view === 'form' && (
        <form onSubmit={handleSubmit} style={{ display: 'contents' }}>
          <DialogTitle sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <IconButton edge='start' onClick={handleSwitchToList} size='small'>
              <ArrowBackIcon />
            </IconButton>
            {editingTarget ? 'Edit Target' : 'Add Target'}
          </DialogTitle>
          <DialogContent dividers>
            <Stack spacing={3} sx={{ mt: 1 }}>
              <TextField
                fullWidth
                id='target-form-name'
                name='name'
                label='Name'
                value={values.name}
                onChange={handleChange}
                error={Boolean(errors.name)}
                helperText={errors.name}
                placeholder='e.g. Production DB'
                autoFocus
              />
              <TextField
                fullWidth
                id='target-form-type'
                name='type'
                label='Type'
                select
                value={values.type}
                onChange={handleChange}
                error={Boolean(errors.type)}
                helperText={errors.type}
              >
                <MenuItem value='duckdb'>DuckDB</MenuItem>
                <MenuItem value='postgres'>Postgres</MenuItem>
                <MenuItem value='snowflake'>Snowflake</MenuItem>
                <MenuItem value='other'>Other</MenuItem>
              </TextField>
              <TextField
                fullWidth
                id='target-form-command'
                name='command'
                label='Command'
                value={values.command}
                onChange={handleChange}
                error={Boolean(errors.command)}
                helperText={errors.command || 'Arguments separated by spaces'}
                multiline
                rows={2}
                placeholder='mcp-server-duckdb --db ./my.db'
                sx={{ fontFamily: 'monospace' }}
              />
              <TextField
                fullWidth
                id='target-form-env'
                name='env'
                label='Environment Variables (JSON)'
                value={values.env}
                onChange={handleChange}
                error={Boolean(errors.env)}
                helperText={errors.env}
                multiline
                rows={4}
                sx={{ fontFamily: 'monospace' }}
              />
            </Stack>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleSwitchToList}>Cancel</Button>
            <Button
              type='submit'
              variant='contained'
              disabled={createMutation.isPending || updateMutation.isPending}
            >
              {editingTarget ? 'Update' : 'Create'}
            </Button>
          </DialogActions>
        </form>
      )}
    </Dialog>
  );
}
