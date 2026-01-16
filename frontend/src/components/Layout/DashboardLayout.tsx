import { Box, useTheme } from "@mui/material";
import { ReactNode } from "react";
import {
  Panel,
  Group as PanelGroup,
  Separator as PanelResizeHandle,
} from "react-resizable-panels";
import { AppHeader } from "./AppHeader";
import type { ObservedStep } from "../../api/types";

interface DashboardLayoutProps {
  sidebar: ReactNode;
  main: ReactNode;
  rightPanel: ReactNode;
  subheader?: ReactNode;
  headerProps: {
    title: string;
    steps: ObservedStep[];
    showBack?: boolean;
    actions?: ReactNode;
  };
}

export function DashboardLayout({
  sidebar,
  main,
  rightPanel,
  subheader,
  headerProps,
}: DashboardLayoutProps) {
  const theme = useTheme();
  const borderColor = theme.palette.divider;

  const Handle = () => (
    <PanelResizeHandle
      style={{
        width: "1px",
        backgroundColor: borderColor,
        transition: "background-color 0.2s",
        cursor: "col-resize",
        flexShrink: 0,
      }}
    />
  );

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
        overflow: "hidden",
        bgcolor: "background.default",
      }}
    >
      <AppHeader {...headerProps} />
      {subheader}

      <Box sx={{ flexGrow: 1, overflow: "hidden" }}>
        <PanelGroup
          orientation="horizontal"
          style={{ height: "100%", width: "100%" }}
        >
          <Panel
            defaultSize="20"
            minSize="15"
            maxSize="30"
            collapsible
            style={{
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {sidebar}
          </Panel>

          <Handle />

          <Panel
            defaultSize="50"
            minSize="30"
            style={{
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {main}
          </Panel>

          <Handle />

          <Panel
            defaultSize="30"
            minSize="20"
            style={{
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {rightPanel}
          </Panel>
        </PanelGroup>
      </Box>
    </Box>
  );
}
