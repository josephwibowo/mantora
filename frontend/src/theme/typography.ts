export const getTypography = () => ({
  fontFamily:
    '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji"',
  h1: { fontSize: '2rem', fontWeight: 600 },
  h2: { fontSize: '1.5rem', fontWeight: 600 },
  h3: { fontSize: '1.25rem', fontWeight: 600 },
  h4: { fontSize: '1rem', fontWeight: 600 },
  h5: { fontSize: '0.875rem', fontWeight: 600 },
  h6: {
    fontSize: '0.75rem',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  body1: { fontSize: '0.875rem' },
  body2: { fontSize: '0.75rem' }, // Denser body text
  button: { textTransform: 'none', fontWeight: 500 },
  code: {
    fontFamily: '"JetBrains Mono", "Fira Code", "Roboto Mono", monospace',
    fontSize: '0.8125rem',
  },
});
