import { createTheme, PaletteMode, ThemeOptions } from '@mui/material';
import { getPalette } from './palette';
import { getTypography } from './typography';
import { getComponents } from './components';

export const getDesignTokens = (mode: PaletteMode): ThemeOptions => {
  // 1. Create a base theme to pass to getComponents (so it can access palette)
  // Note: This is a slight circular dependency workaround or we just use simple logic in components
  // For simplicity, we just pass the mode-aware palette objects to overrides if needed,
  // or we construct the theme in two passes.

  // Pass 1: Palette & Typography
  const palette = getPalette(mode);
  const typography = getTypography();

  // Pass 2: Components (need access to resolved palette colors in some cases)
  // We can't access `theme.palette` easily inside `createTheme` without custom logic.
  // Instead, we'll allow `getComponents` to take a partial theme or just the palette values it needs.
  // Actually, MUI's `createTheme` doesn't expose `theme` to overrides directly in the options object relative to itself.
  // But we can approximate.

  return {
    palette,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    typography: typography as any, // Cast to avoid strict type checks on custom variants if any
    shape: {
      borderRadius: 6,
    },
    // We will merge components later or assume static colors for now in `components.ts`
    // OR better: Return options.
  };
};

export const createAppTheme = (mode: PaletteMode) => {
  const tokens = getDesignTokens(mode);
  let theme = createTheme(tokens);

  // Now apply component overrides which might depend on the theme
  theme = createTheme(theme, {
    components: getComponents(theme),
  });

  return theme;
};
