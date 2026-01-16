import { useState, useMemo } from "react";
import {
  Alert,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TableSortLabel,
  TextField,
  Typography,
} from "@mui/material";

import type { Cast } from "../api/types";
import { copyToClipboard } from "../utils/clipboard";
import { rowsToMarkdownTable } from "../utils/markdown";
import { ArtifactTile } from "./Artifacts/ArtifactTile";

type Props = {
  cast: Cast;
  onStepClick?: (stepId: string) => void;
};

type SortDirection = "asc" | "desc";

export function TableCast({ cast, onStepClick }: Props) {
  const [filterText, setFilterText] = useState("");
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const rows = useMemo(() => cast.rows ?? [], [cast.rows]);
  const columns = useMemo(
    () => (rows.length > 0 ? Object.keys(rows[0]) : []),
    [rows],
  );
  const columnsInfo = useMemo(() => cast.columns ?? [], [cast.columns]);

  // Build column type map
  const columnTypes = useMemo(() => {
    const typeMap: Record<string, string | null> = {};
    columnsInfo.forEach((col) => {
      typeMap[col.name] = col.type;
    });
    return typeMap;
  }, [columnsInfo]);

  // Apply filter and sort
  const processedRows = useMemo(() => {
    let result = [...rows];

    // Filter
    if (filterText.trim()) {
      const lowerFilter = filterText.toLowerCase();
      result = result.filter((row) =>
        Object.values(row).some((val) =>
          String(val).toLowerCase().includes(lowerFilter),
        ),
      );
    }

    // Sort
    if (sortColumn) {
      result.sort((a, b) => {
        const aVal = a[sortColumn];
        const bVal = b[sortColumn];

        // Handle nulls
        if (aVal == null && bVal == null) return 0;
        if (aVal == null) return 1;
        if (bVal == null) return -1;

        // Try numeric comparison first
        const aNum = Number(aVal);
        const bNum = Number(bVal);
        if (!isNaN(aNum) && !isNaN(bNum)) {
          return sortDirection === "asc" ? aNum - bNum : bNum - aNum;
        }

        // String comparison
        const aStr = String(aVal);
        const bStr = String(bVal);
        const cmp = aStr.localeCompare(bStr);
        return sortDirection === "asc" ? cmp : -cmp;
      });
    }

    return result;
  }, [rows, filterText, sortColumn, sortDirection]);

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortColumn(column);
      setSortDirection("asc");
    }
  };

  const handleCopySQL = async () => {
    if (!cast.sql) return;
    try {
      await copyToClipboard(cast.sql);
    } catch (err) {
      console.error("Failed to copy SQL:", err);
    }
  };

  const handleCopyMarkdown = async () => {
    const markdown = rowsToMarkdownTable(
      processedRows,
      columns,
      cast.truncated,
    );
    try {
      await copyToClipboard(markdown);
    } catch (err) {
      console.error("Failed to copy markdown:", err);
    }
  };

  return (
    <ArtifactTile
      title={cast.title}
      type="TABLE"
      onCopyMarkdown={handleCopyMarkdown}
      onCopySQL={cast.sql ? handleCopySQL : undefined}
    >
      <Box sx={{ p: 2 }}>
        {cast.truncated && (
          <Alert
            severity="info"
            sx={{ mb: 2, py: 0, px: 2, alignItems: "center" }}
          >
            Showing first {rows.length} of {cast.total_rows ?? "?"} rows
          </Alert>
        )}

        <TextField
          size="small"
          placeholder="Filter rows..."
          value={filterText}
          onChange={(e) => setFilterText(e.target.value)}
          sx={{ mb: 2, width: 300, display: rows.length > 5 ? "flex" : "none" }}
        />

        <TableContainer
          sx={{ border: 1, borderColor: "divider", borderRadius: 1 }}
        >
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                {columns.map((col) => (
                  <TableCell
                    key={col}
                    sx={{ fontWeight: 600, bgcolor: "background.default" }}
                  >
                    <TableSortLabel
                      active={sortColumn === col}
                      direction={sortColumn === col ? sortDirection : "asc"}
                      onClick={() => handleSort(col)}
                    >
                      <Box>
                        <Typography
                          variant="body2"
                          sx={{ fontWeight: 600, fontSize: "0.75rem" }}
                        >
                          {col}
                        </Typography>
                        {columnTypes[col] && (
                          <Typography
                            variant="caption"
                            sx={{ color: "text.secondary", fontSize: "0.7rem" }}
                          >
                            {columnTypes[col]}
                          </Typography>
                        )}
                      </Box>
                    </TableSortLabel>
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {processedRows.map((row, idx) => (
                <TableRow key={idx} hover>
                  {columns.map((col) => (
                    <TableCell
                      key={col}
                      sx={{ fontSize: "0.8rem", fontFamily: "monospace" }}
                    >
                      {String(row[col] ?? "")}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>

        <Typography
          variant="caption"
          sx={{
            mt: 1,
            display: "block",
            color: "text.secondary",
            cursor: "pointer",
            textAlign: "right",
          }}
          onClick={() => onStepClick?.(cast.origin_step_id)}
        >
          Linked Evidence: {cast.origin_step_id.slice(0, 8)}...
        </Typography>
      </Box>
    </ArtifactTile>
  );
}
