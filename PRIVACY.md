# Privacy

## TL;DR
Mantora is **local-first**. By default, it records sessions **only on your machine** and does not send your data anywhere.
Any sharing (reports/exports) is **user-initiated**.

## What Mantora stores
Mantora may store the following locally to help you verify and reproduce agent behavior:

- Session metadata (timestamps, duration, target type)
- Tool calls and SQL text executed through Mantora
- Safety decisions (allowed / warned / blocked) and rule match details
- Result metadata (e.g., row counts, column names/types)  
- **Capped result previews** (Mantora stores a limited number of rows/bytes per result as evidence; this is configurable via `preview_rows` and `preview_bytes`).
- Optional git context (repo name, branch, commit hash, dirty status) resolved from the working directory.
- Optional user tags (e.g., ticket IDs) provided via the CLI or UI.

## Where data is stored
By default, Mantora stores data in your home directory:
- `~/.mantora/` (macOS/Linux)
- `%USERPROFILE%\.mantora\` (Windows)

This includes:
- A local SQLite database: `sessions.db`
- Local application logs (if enabled).

## What Mantora does NOT do
- No automatic upload of queries, results, or session logs.
- No background collection of files outside what you route through Mantora.
- No tracking or telemetry across applications.
- **No data leaves your machine** unless you explicitly export or share it.

## Network access / telemetry
By default, Mantora makes **no outbound network requests**.
If optional telemetry or error reporting is added or enabled, it will be documented here along with opt-out instructions.

## Reports and exports
Reports (Markdown) and exports (JSON) are generated locally. They may contain sensitive SQL and metadata.
You are responsible for reviewing and redacting content before sharing externally.

## Retention and deletion
Recorded data is retained until you delete it.
To delete all local data, remove the Mantora data directory:
- `rm -rf ~/.mantora` (macOS/Linux)
(or the equivalent on your OS)

## Changes
If this privacy policy changes, it will be updated in the repository and released with notes in the changelog.

## Contact
For questions or concerns, open an issue in the repository.
