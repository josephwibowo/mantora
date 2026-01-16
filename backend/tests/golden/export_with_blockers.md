# Session: demo
- ID: `00000000-0000-0000-0000-000000000001`
- Created: `2026-01-01T00:00:00+00:00`
- Steps: 3 (of 3)
- Casts: 0 (of 0)

## Summary

- Tool calls: 0
- Queries: 2
- Casts: 0
- Blocks: 1
- Errors: 0
- Warnings: 0

## Timeline

### 1. query

- Step ID: `00000000-0000-0000-0000-000000000101`
- At: `2026-01-01T00:01:00+00:00`
- Kind: `blocker`
- Status: `ok`
- Risk: `CRITICAL`
- Summary: Blocked: Destructive SQL is not allowed in protective mode

- Pending request: `00000000-0000-0000-0000-000000000099`
- Reason: Destructive SQL is not allowed in protective mode

**SQL**

```sql
DROP TABLE users
```

**Args (JSON)**

```json
{
  "classification": "destructive",
  "reason": "Destructive SQL is not allowed in protective mode",
  "request_id": "00000000-0000-0000-0000-000000000099",
  "risk_level": "CRITICAL",
  "sql": "DROP TABLE users"
}
```

### 2. query

- Step ID: `00000000-0000-0000-0000-000000000102`
- At: `2026-01-01T00:02:00+00:00`
- Kind: `blocker_decision`
- Status: `ok`
- Risk: `CRITICAL`
- Summary: Denied blocked query request

- Pending request: `00000000-0000-0000-0000-000000000099`
- Decision: `denied`
- Reason: Destructive SQL is not allowed in protective mode

**SQL**

```sql
DROP TABLE users
```

**Args (JSON)**

```json
{
  "classification": "destructive",
  "decision": "denied",
  "reason": "Destructive SQL is not allowed in protective mode",
  "request_id": "00000000-0000-0000-0000-000000000099",
  "risk_level": "CRITICAL",
  "sql": "DROP TABLE users"
}
```

### 3. note

- Step ID: `00000000-0000-0000-0000-000000000103`
- At: `2026-01-01T00:03:00+00:00`
- Kind: `note`
- Status: `ok`

**Args (JSON)**

```json
{
  "hello": "world"
}
```

**Result (JSON)**

```json
{
  "ok": true
}
```


## Casts

_No casts._
