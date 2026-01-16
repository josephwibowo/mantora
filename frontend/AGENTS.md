# Frontend Coding Standards

## Core Stack

**Vite • React 18 • TypeScript • MUI v5 • TanStack Query • Vega-Lite**

## TypeScript & Components

1. **Strict Typing**: No `any`. Use discriminated unions for state (e.g., `kind: 'table' | 'chart'`).
2. **Props Interfaces**: Explicitly define `interface Props` for every component.
3. **Derived State**: Avoid `useEffect` for state sync. derive values during render or use `useMemo`.
4. **Files**: One component per file. Named exports preferred.

## Material UI (MUI)

1. **Styling**:
   - Use the `sx={{ ... }}` prop for one-off styles.
   - Use `styled(Box)(({ theme }) => ({}))` for reusable components.
   - **Never** use `makeStyles` or `withStyles` (legacy).
2. **Theming**: Always use theme tokens (e.g., `theme.palette.primary.main`), never hardcoded hex values.
3. **Layout**: Prefer `<Stack>` and `<Box>` over `<div>`.

## Data Fetching (TanStack Query)

1. **Custom Hooks**: Encapsulate queries in `src/api/queries.ts` or custom hooks (e.g., `useSession`).
2. **Server State**: Do not copy query data into local `useState`. Use the `data` from the hook directly.
3. **Mutations**: Invalidate relevant query keys on success.

## Mantora Patterns

1. **Evidence Linking**: All artifact components (Charts, Tables) **MUST** accept an `origin_step_id` to link back to the source tool call.
2. **Truncation**: UI must defensively handle large inputs. Truncate text/rows aggressively and offer a "full view" or "copy" action.
3. **Copyable**: Any code, SQL, or markdown output must have a "Copy" button.
