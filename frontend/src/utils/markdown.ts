/**
 * Convert table rows to GitHub-flavored Markdown table format.
 *
 * @param rows - Array of row objects
 * @param columns - Array of column names (ordered)
 * @param truncated - Whether the data is truncated
 * @returns Markdown table string
 */
export function rowsToMarkdownTable(
  rows: Record<string, unknown>[],
  columns: string[],
  truncated: boolean = false,
): string {
  if (rows.length === 0 || columns.length === 0) {
    return '';
  }

  // Header row
  const header = `| ${columns.join(' | ')} |`;

  // Separator row
  const separator = `| ${columns.map(() => '---').join(' | ')} |`;

  // Data rows
  const dataRows = rows.map((row) => {
    const cells = columns.map((col) => {
      const value = row[col];
      // Format value for markdown (escape pipes, handle nulls)
      if (value === null || value === undefined) {
        return 'null';
      }
      return String(value).replace(/\|/g, '\\|').replace(/\n/g, ' ');
    });
    return `| ${cells.join(' | ')} |`;
  });

  const lines = [header, separator, ...dataRows];

  if (truncated) {
    lines.push('');
    lines.push('*Note: Data has been truncated for display*');
  }

  return lines.join('\n');
}
