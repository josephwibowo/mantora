# Architecture

Mantora is designed as a modular, local-first MCP proxy. It is built to be a standalone binary that can act as both a server and a client in the MCP ecosystem.

## High-Level Overview

```mermaid
flowchart LR
    subgraph Agent [AI Agent]
        Client[Claude / Cursor]
    end

    subgraph Mantora [Mantora System]
        direction TB
        Proxy[Observer / Proxy]
        Policy[Policy Engine]
        Store[(SQLite Session Store)]
        
        Proxy -- "Checks Safety" --> Policy
        Policy -- "Returns Verdict" --> Proxy
        Proxy -- "Logs Events" --> Store
    end

    subgraph Backend [Target Database]
        Target[MCP Server\n(DuckDB / Postgres)]
    end

    subgraph Frontend [User Interface]
        UI[Mantora UI\n(Browser)]
    end

    Client <==>|"MCP (JSON-RPC)"| Proxy
    Proxy <==>|"MCP (JSON-RPC)"| Target
    UI <== "Reads History" ==> Store
```

1.  **Client:** The AI agent (e.g., Claude Desktop or Cursor).
2.  **Proxy (The "Observer"):** Intercepts JSON-RPC 2.0 messages. It parses tool calls (specifically knowing about SQL dialects) to enforce policy.
3.  **Target:** The actual database MCP server. Mantora can spawn this itself ("Direct Mode") or wrap an existing process via stdio ("Wrappper Mode").
4.  **Store:** A local SQLite database (`sessions.db`) that persists the entire conversation history, tool inputs/outputs, and policy decisions.
5.  **UI:** A React/Vite web application that queries the Store to visualize sessions.

## Core Domains

The codebase is organized into four main functional areas:

### 1. Observer (`backend/src/mantora/observer`)
The heart of the system.
*   **Proxy Logic:** Handles the MCP protocol handshake and message routing.
*   **Connectors:** Specific adapters for different databases (DuckDB, Postgres) to understand their specific SQL dialects and tool definitions.

### 2. Policy (`backend/src/mantora/policy`)
The decision engine.
*   **SQL Guard:** Regex and heuristic-based analysis of SQL strings.
*   **Blocker:** Logic to determine if a call should proceed or be halted based on `config.toml`.

### 3. Store (`backend/src/mantora/store`)
The persistence layer.
*   **Schema:** Uses SQLModel/SQLAlchemy to define `Session`, `Step`, `Event`, and `Artifact` tables.
*   **Export:** Logic to serialize sessions into Markdown reports or JSON.

### 4. UI (`backend/src/mantora/api` + `frontend/`)
The user interface.
*   **API:** A FastAPI server that exposes the SQLite data via REST endpoints.
*   **Frontend:** A modern React application for browsing traces.

## Design Principles

*   **Local-First:** No data leaves the machine. No reliance on cloud services for the core loop.
*   **Stream-Based:** Traces are captured in real-time.
*   **Fail-Safe:** If the UI crashes, the proxy continues to work. If the proxy crashes, the agent session ends safely. (In "Proxy Mode", if the underlying server crashes, Mantora reports it).

## Tech Stack

*   **Backend:** Python 3.12+, FastAPI, Uvicorn, SQLAlchemy (Async), Pydantic.
*   **Frontend:** TypeScript, React, Vite, TanStack Query, Tailwind CSS (via components).
*   **Packaging:** `pipx` or `uv` for easy installation of the Python CLI.
