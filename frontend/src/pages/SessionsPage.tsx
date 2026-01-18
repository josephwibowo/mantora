import {
  Box,
  Button,
  Chip,
  Container,
  IconButton,
  InputBase,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  Tooltip,
  Typography,
  useTheme,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import SearchIcon from '@mui/icons-material/Search';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import ErrorIcon from '@mui/icons-material/Error';
import BlockIcon from '@mui/icons-material/Block';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { ChangeEvent, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  useCreateSession,
  useDeleteSession,
  useSessions,
  useSessionsSummaries,
} from '../api/queries';
import { AppHeader } from '../components/Layout/AppHeader';
import type { Session } from '../api/types';

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

export function SessionsPage() {
  const navigate = useNavigate();
  const theme = useTheme();
  const { data: sessions, isLoading, error } = useSessions();
  const createSession = useCreateSession();
  const deleteSession = useDeleteSession();
  const [title, setTitle] = useState('');
  const [filter, setFilter] = useState('');
  const [hoveredRowId, setHoveredRowId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [sessionToDelete, setSessionToDelete] = useState<string | null>(null);

  const handleCreate = () => {
    createSession.mutateAsync(title.trim() ? title.trim() : null).then((newSession) => {
      if (newSession && newSession.id) {
        navigate(`/sessions/${newSession.id}`);
      }
    });
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !createSession.isPending) {
      handleCreate();
    }
  };

  const handleDeleteClick = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation(); // Prevent row click navigation
    setSessionToDelete(sessionId);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (sessionToDelete) {
      try {
        await deleteSession.mutateAsync(sessionToDelete);
      } catch (error) {
        console.error('Failed to delete session:', error);
      } finally {
        setDeleteDialogOpen(false);
        setSessionToDelete(null);
      }
    }
  };

  const cancelDelete = () => {
    setDeleteDialogOpen(false);
    setSessionToDelete(null);
  };

  const filteredSessions = (sessions ?? []).filter(
    (s) => !filter || s.title?.toLowerCase().includes(filter.toLowerCase()),
  );
  const sessionSummaries = useSessionsSummaries(filteredSessions.map((s) => s.id));

  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: 'background.default',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <AppHeader title='Dashboard' />

      <Container
        maxWidth='lg'
        sx={{ py: 4, flexGrow: 1, display: 'flex', flexDirection: 'column' }}
      >
        {/* Toolbar */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Paper
            elevation={0}
            variant='outlined'
            sx={{
              p: '4px 12px',
              display: 'flex',
              alignItems: 'center',
              flexGrow: 1,
              maxWidth: 400,
              borderRadius: 2,
              borderColor: theme.palette.divider,
              bgcolor: 'background.paper',
            }}
          >
            <SearchIcon sx={{ color: 'text.secondary', mr: 1, fontSize: 20 }} />
            <InputBase
              sx={{ flex: 1, fontSize: '0.875rem' }}
              placeholder='Search sessions...'
              value={filter}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setFilter(e.target.value)}
            />
          </Paper>

          <Box sx={{ flexGrow: 1 }} />

          <Paper
            elevation={0}
            variant='outlined'
            sx={{
              p: '4px 8px',
              display: 'flex',
              alignItems: 'center',
              borderRadius: 2,
              borderColor: theme.palette.divider,
              bgcolor: 'background.paper',
              transition: 'box-shadow 0.2s',
              '&:focus-within': {
                boxShadow: `0 0 0 2px ${theme.palette.primary.main}`,
                borderColor: 'primary.main',
              },
            }}
          >
            <InputBase
              sx={{ ml: 1, flex: 1, fontSize: '0.875rem', minWidth: 200 }}
              placeholder='New session name (optional)...'
              value={title}
              onChange={(e: ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <Button
              variant='contained'
              size='small'
              onClick={handleCreate}
              disabled={createSession.isPending}
              startIcon={<AddIcon />}
              sx={{
                ml: 1,
                textTransform: 'none',
                fontWeight: 600,
                borderRadius: 1.5,
              }}
            >
              {createSession.isPending ? 'Creating...' : 'New Session'}
            </Button>
          </Paper>
        </Box>

        {/* Sessions Table */}
        <TableContainer component={Paper} variant='outlined' sx={{ borderRadius: 2, flexGrow: 1 }}>
          <Table size='small' stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell
                  sx={{
                    fontWeight: 700,
                    bgcolor: 'background.default',
                    width: 60,
                    textAlign: 'center',
                  }}
                >
                  Status
                </TableCell>
                <TableCell sx={{ fontWeight: 700, bgcolor: 'background.default' }}>
                  Session Name
                </TableCell>
                <TableCell
                  sx={{
                    fontWeight: 700,
                    bgcolor: 'background.default',
                    width: 120,
                  }}
                >
                  ID
                </TableCell>
                <TableCell
                  sx={{
                    fontWeight: 700,
                    bgcolor: 'background.default',
                    width: 140,
                  }}
                >
                  Created
                </TableCell>
                <TableCell
                  sx={{
                    fontWeight: 700,
                    bgcolor: 'background.default',
                    width: 50,
                  }}
                ></TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {isLoading ? (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color='text.secondary' sx={{ py: 4, textAlign: 'center' }}>
                      Loading sessions...
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : error ? (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color='error' sx={{ py: 4, textAlign: 'center' }}>
                      Error loading sessions.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : filteredSessions.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5}>
                    <Typography color='text.secondary' sx={{ py: 4, textAlign: 'center' }}>
                      No sessions found.
                    </Typography>
                  </TableCell>
                </TableRow>
              ) : (
                filteredSessions.map((s: Session) => (
                  <TableRow
                    key={s.id}
                    hover
                    onClick={() => navigate(`/sessions/${s.id}`)}
                    onMouseEnter={() => setHoveredRowId(s.id)}
                    onMouseLeave={() => setHoveredRowId(null)}
                    sx={{
                      cursor: 'pointer',
                      '&:hover': { bgcolor: 'action.hover' },
                    }}
                  >
                    <TableCell align='center'>
                      {(() => {
                        const summary = sessionSummaries.data?.[s.id];
                        if (!summary) {
                          return <CheckCircleIcon sx={{ color: 'text.disabled', fontSize: 18 }} />;
                        }
                        if (summary.errors > 0) {
                          return <ErrorIcon sx={{ color: 'error.main', fontSize: 18 }} />;
                        }
                        if (summary.blocks > 0) {
                          return <BlockIcon sx={{ color: 'warning.main', fontSize: 18 }} />;
                        }
                        if (summary.warnings > 0) {
                          return <WarningAmberIcon sx={{ color: 'warning.main', fontSize: 18 }} />;
                        }
                        return <CheckCircleIcon sx={{ color: 'success.main', fontSize: 18 }} />;
                      })()}
                    </TableCell>
                    <TableCell>
                      <Typography variant='body2' fontWeight={600}>
                        {s.title || 'Untitled Session'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={`#${s.id.slice(0, 6)}`}
                        size='small'
                        sx={{
                          fontFamily: 'monospace',
                          fontSize: '0.7rem',
                          height: 22,
                          bgcolor: 'action.hover',
                          borderRadius: 1,
                        }}
                      />
                    </TableCell>
                    <TableCell>
                      <Tooltip
                        title={new Date(s.created_at).toLocaleString()}
                        arrow
                        placement='top'
                      >
                        <Typography
                          variant='caption'
                          color='text.secondary'
                          fontFamily='monospace'
                          sx={{ cursor: 'help' }}
                        >
                          {formatRelativeTime(s.created_at)}
                        </Typography>
                      </Tooltip>
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size='small'
                        onClick={(e) => handleDeleteClick(e, s.id)}
                        disabled={deleteSession.isPending}
                        sx={{
                          opacity: hoveredRowId === s.id ? 1 : 0,
                          transition: 'opacity 0.15s, color 0.15s',
                          color: 'text.secondary',
                          '&:hover': {
                            color: 'error.main',
                            bgcolor: 'rgba(211, 47, 47, 0.08)', // Subtle red background
                          },
                        }}
                      >
                        <DeleteOutlineIcon fontSize='small' />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>

        {/* Delete Confirmation Dialog */}
        <Dialog
          open={deleteDialogOpen}
          onClose={cancelDelete}
          aria-labelledby='delete-dialog-title'
          aria-describedby='delete-dialog-description'
        >
          <DialogTitle id='delete-dialog-title'>Delete Session?</DialogTitle>
          <DialogContent>
            <DialogContentText id='delete-dialog-description'>
              Are you sure you want to delete this session? This action cannot be undone.
            </DialogContentText>
          </DialogContent>
          <DialogActions>
            <Button onClick={cancelDelete} color='inherit'>
              Cancel
            </Button>
            <Button onClick={confirmDelete} color='error' variant='contained' autoFocus>
              Delete
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  );
}
