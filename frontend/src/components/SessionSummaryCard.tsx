import { useMemo, useState, useRef } from 'react';
import {
  Alert,
  Box,
  Button,
  ButtonGroup,
  ClickAwayListener,
  Chip,
  Divider,
  Grow,
  InputBase,
  ListItemIcon,
  ListItemText,
  ListSubheader,
  MenuItem,
  MenuList,
  Paper,
  Popper,
  Snackbar,
  Stack,
  Switch,
  Typography,
} from '@mui/material';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import DataObjectIcon from '@mui/icons-material/DataObject';

import type { Session, SessionSummary } from '../api/types';

interface SessionSummaryCardProps {
  session: Session;
  rollup: SessionSummary | null;
  isLoading: boolean;
  onCopyForPr: () => Promise<void>;
  onCopyPlain: () => Promise<void>;
  onExportMd: () => void;
  onExportJson: () => void;
  includeData: boolean;
  onIncludeDataChange: (checked: boolean) => void;
  onSaveRepoRoot: (repoRoot: string | null) => Promise<void>;
  onSaveTag: (tag: string | null) => Promise<void>;
  isCopying: boolean;
  isSavingRepoRoot: boolean;
  isSavingTag: boolean;
}

type Status = 'clean' | 'warnings' | 'blocked';

function deriveStatus(rollup: SessionSummary | null): Status {
  if (!rollup) return 'clean';
  if (rollup.status === 'blocked' || rollup.blocks > 0) return 'blocked';
  if (rollup.status === 'warnings' || rollup.warnings > 0) return 'warnings';
  return 'clean';
}

export function SessionSummaryCard({
  session,
  rollup,
  isLoading,
  onCopyForPr,
  onCopyPlain,
  onExportMd,
  onExportJson,
  includeData,
  onIncludeDataChange,
  onSaveRepoRoot,
  onSaveTag,
  isCopying,
  isSavingRepoRoot,
  isSavingTag,
}: SessionSummaryCardProps) {
  const [copyError, setCopyError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const currentTag = session.context?.tag ?? '';
  const [draftTag, setDraftTag] = useState(currentTag);
  const [tagError, setTagError] = useState<string | null>(null);
  const currentRepoRoot = session.context?.repo_root ?? '';
  const [draftRepoRoot, setDraftRepoRoot] = useState(currentRepoRoot);
  const [repoRootError, setRepoRootError] = useState<string | null>(null);

  // Split button state
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement>(null);

  const status = deriveStatus(rollup);
  const tablesTouched = rollup?.tables_touched ?? null;
  const duration = rollup?.duration_ms_total ?? null;
  const ctx = session.context ?? null;

  const contextLine = useMemo(() => {
    const parts = [ctx?.repo_name, ctx?.branch, ctx?.tag].filter(Boolean) as string[];
    return parts.length > 0 ? parts.join(' • ') : null;
  }, [ctx?.branch, ctx?.repo_name, ctx?.tag]);

  const statusChip = (
    <Chip
      size='small'
      label={status.toUpperCase()}
      color={status === 'clean' ? 'success' : status === 'warnings' ? 'warning' : 'error'}
      sx={{ borderRadius: 1.5, fontWeight: 700 }}
    />
  );

  const handleCopy = async () => {
    setOpen(false); // Close menu if open to prevent layout shift
    setCopyError(null);
    setCopied(false);
    try {
      await onCopyForPr();
      setCopied(true);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to copy report';
      setCopyError(message);
    }
  };

  const handleCopyClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
    if (reason === 'clickaway') {
      return;
    }
    setCopied(false);
  };

  const handleMenuItemClick = (
    event: React.MouseEvent<HTMLLIElement, MouseEvent>,
    action: () => void | Promise<void>,
  ) => {
    void action();
    setOpen(false);
  };

  const handleToggle = () => {
    setOpen((prevOpen) => !prevOpen);
  };

  const handleClose = (event: Event) => {
    if (anchorRef.current && anchorRef.current.contains(event.target as HTMLElement)) {
      return;
    }
    setOpen(false);
  };

  const trimmedTag = draftTag.trim();
  const tagDirty = trimmedTag !== currentTag;
  const handleSaveTag = async () => {
    setTagError(null);
    try {
      await onSaveTag(trimmedTag.length > 0 ? trimmedTag : null);
      setDraftTag(trimmedTag);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update tag';
      setTagError(message);
    }
  };

  const trimmedRepoRoot = draftRepoRoot.trim();
  const repoRootDirty = trimmedRepoRoot !== currentRepoRoot;
  const handleSaveRepoRoot = async () => {
    setRepoRootError(null);
    try {
      await onSaveRepoRoot(trimmedRepoRoot.length > 0 ? trimmedRepoRoot : null);
      setDraftRepoRoot(trimmedRepoRoot);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update repo';
      setRepoRootError(message);
    }
  };

  return (
    <Paper variant='outlined' sx={{ borderRadius: 2, p: 2, bgcolor: 'background.paper' }}>
      <Stack spacing={1.25}>
        <Stack direction='row' alignItems='center' justifyContent='space-between' spacing={2}>
          {/* ... keeping header part same ... */}
          <Box>
            <Stack direction='row' spacing={1} alignItems='center'>
              <Typography variant='subtitle2' fontWeight={800}>
                Session Summary
              </Typography>
              {statusChip}
            </Stack>
            {contextLine && (
              <Typography variant='caption' color='text.secondary' fontFamily='monospace'>
                {contextLine}
              </Typography>
            )}
          </Box>

          <Stack direction='row' spacing={1} alignItems='center'>
            <ButtonGroup variant='contained' ref={anchorRef} aria-label='split button'>
              <Button
                size='small'
                startIcon={<ContentCopyIcon />}
                onClick={handleCopy}
                disabled={isCopying}
                sx={{ textTransform: 'none', fontWeight: 700 }}
              >
                {isCopying ? 'Copying…' : 'Copy report (.md)'}
              </Button>
              <Button
                size='small'
                aria-controls={open ? 'split-button-menu' : undefined}
                aria-expanded={open ? 'true' : undefined}
                aria-label='select merge strategy'
                aria-haspopup='menu'
                onClick={handleToggle}
              >
                <ArrowDropDownIcon />
              </Button>
            </ButtonGroup>
            <Popper
              sx={{ zIndex: 1 }}
              open={open}
              anchorEl={anchorRef.current}
              role={undefined}
              transition
              disablePortal
            >
              {({ TransitionProps, placement }) => (
                <Grow
                  {...TransitionProps}
                  style={{
                    transformOrigin: placement === 'bottom' ? 'center top' : 'center bottom',
                  }}
                >
                  <Paper sx={{ minWidth: 220 }}>
                    <ClickAwayListener onClickAway={handleClose}>
                      <MenuList id='split-button-menu' autoFocusItem={open}>
                        {/* 1. Settings Section */}
                        <ListSubheader disableSticky sx={{ lineHeight: '32px' }}>
                          Options
                        </ListSubheader>
                        <MenuItem
                          onClick={() => {
                            // Don't close menu when toggling switch
                            onIncludeDataChange(!includeData);
                          }}
                        >
                          <ListItemIcon>
                            <Switch
                              size='small'
                              checked={includeData}
                              onChange={(e) => onIncludeDataChange(e.target.checked)}
                              onClick={(e) => e.stopPropagation()}
                            />
                          </ListItemIcon>
                          <ListItemText primary='Include sample data' />
                        </MenuItem>

                        <Divider />

                        {/* 2. Copy Section */}
                        <ListSubheader disableSticky sx={{ lineHeight: '32px' }}>
                          Copy
                        </ListSubheader>
                        <MenuItem
                          onClick={(event) => handleMenuItemClick(event, () => onCopyPlain())}
                        >
                          <ListItemIcon>
                            <ContentCopyIcon fontSize='small' />
                          </ListItemIcon>
                          <ListItemText primary='Copy report (Plain)' />
                        </MenuItem>

                        <Divider />

                        {/* 3. Download Section */}
                        <ListSubheader disableSticky sx={{ lineHeight: '32px' }}>
                          Download
                        </ListSubheader>
                        <MenuItem onClick={(event) => handleMenuItemClick(event, onExportMd)}>
                          <ListItemIcon>
                            <FileDownloadIcon fontSize='small' />
                          </ListItemIcon>
                          <ListItemText primary='Download report (.md)' />
                        </MenuItem>
                        <MenuItem onClick={(event) => handleMenuItemClick(event, onExportJson)}>
                          <ListItemIcon>
                            <DataObjectIcon fontSize='small' />
                          </ListItemIcon>
                          <ListItemText primary='Download session JSON' />
                        </MenuItem>
                      </MenuList>
                    </ClickAwayListener>
                  </Paper>
                </Grow>
              )}
            </Popper>
          </Stack>
        </Stack>

        {copyError && <Alert severity='error'>{copyError}</Alert>}
        {repoRootError && <Alert severity='error'>{repoRootError}</Alert>}
        {tagError && <Alert severity='error'>{tagError}</Alert>}

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: 'repeat(2, 1fr)', md: 'repeat(6, 1fr)' },
            gap: 1,
          }}
        >
          <Stat label='Tools' value={rollup?.tool_calls ?? null} isLoading={isLoading} />
          <Stat label='Queries' value={rollup?.queries ?? null} isLoading={isLoading} />
          <Stat label='Casts' value={rollup?.casts ?? null} isLoading={isLoading} />
          <Stat label='Blocks' value={rollup?.blocks ?? null} isLoading={isLoading} />
          <Stat label='Warnings' value={rollup?.warnings ?? null} isLoading={isLoading} />
          <Stat label='Errors' value={rollup?.errors ?? null} isLoading={isLoading} />
        </Box>

        <Stack direction='row' spacing={2} sx={{ flexWrap: 'wrap' }}>
          {duration !== null && (
            <Typography variant='caption' color='text.secondary' fontFamily='monospace'>
              Duration: {duration}ms
            </Typography>
          )}
          {tablesTouched && tablesTouched.length > 0 && (
            <Typography variant='caption' color='text.secondary' fontFamily='monospace'>
              Tables: {tablesTouched.length}
            </Typography>
          )}
        </Stack>

        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1}
          alignItems={{ xs: 'stretch', md: 'center' }}
        >
          <Typography
            variant='caption'
            color='text.secondary'
            fontFamily='monospace'
            sx={{ minWidth: 48 }}
          >
            REPO
          </Typography>
          <Paper
            variant='outlined'
            sx={{
              px: 1,
              py: 0.25,
              display: 'flex',
              alignItems: 'center',
              flexGrow: 1,
              borderRadius: 1.5,
              bgcolor: 'background.default',
            }}
          >
            <InputBase
              value={draftRepoRoot}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                setDraftRepoRoot(event.target.value)
              }
              placeholder='Set repo root (path)…'
              sx={{ flex: 1, fontFamily: 'monospace', fontSize: '0.85rem' }}
              onKeyDown={(event: React.KeyboardEvent) => {
                if (event.key === 'Enter' && repoRootDirty && !isSavingRepoRoot) {
                  event.preventDefault();
                  handleSaveRepoRoot();
                }
              }}
            />
          </Paper>
          <Button
            size='small'
            variant='outlined'
            onClick={handleSaveRepoRoot}
            disabled={!repoRootDirty || isSavingRepoRoot}
            sx={{ textTransform: 'none', fontWeight: 700, borderRadius: 1.5 }}
          >
            {isSavingRepoRoot ? 'Saving…' : 'Save'}
          </Button>
        </Stack>

        <Stack
          direction={{ xs: 'column', md: 'row' }}
          spacing={1}
          alignItems={{ xs: 'stretch', md: 'center' }}
        >
          <Typography
            variant='caption'
            color='text.secondary'
            fontFamily='monospace'
            sx={{ minWidth: 48 }}
          >
            TAG
          </Typography>
          <Paper
            variant='outlined'
            sx={{
              px: 1,
              py: 0.25,
              display: 'flex',
              alignItems: 'center',
              flexGrow: 1,
              borderRadius: 1.5,
              bgcolor: 'background.default',
            }}
          >
            <InputBase
              value={draftTag}
              onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                setDraftTag(event.target.value)
              }
              placeholder='Add tag…'
              sx={{ flex: 1, fontFamily: 'monospace', fontSize: '0.85rem' }}
              onKeyDown={(event: React.KeyboardEvent) => {
                if (event.key === 'Enter' && tagDirty && !isSavingTag) {
                  event.preventDefault();
                  handleSaveTag();
                }
              }}
            />
          </Paper>
          <Button
            size='small'
            variant='outlined'
            onClick={handleSaveTag}
            disabled={!tagDirty || isSavingTag}
            sx={{ textTransform: 'none', fontWeight: 700, borderRadius: 1.5 }}
          >
            {isSavingTag ? 'Saving…' : 'Save'}
          </Button>
        </Stack>
      </Stack>
      <Snackbar
        open={copied}
        autoHideDuration={3000}
        onClose={handleCopyClose}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCopyClose} severity='success' sx={{ width: '100%' }}>
          Copied report to clipboard.
        </Alert>
      </Snackbar>
    </Paper>
  );
}

interface StatProps {
  label: string;
  value: number | null;
  isLoading: boolean;
}

function Stat({ label, value, isLoading }: StatProps) {
  return (
    <Box
      sx={{
        px: 1,
        py: 0.75,
        borderRadius: 1.5,
        border: 1,
        borderColor: 'divider',
        bgcolor: 'background.default',
      }}
    >
      <Typography variant='caption' color='text.secondary'>
        {label}
      </Typography>
      <Typography variant='body2' fontWeight={800} fontFamily='monospace'>
        {isLoading ? '…' : (value ?? 0)}
      </Typography>
    </Box>
  );
}
