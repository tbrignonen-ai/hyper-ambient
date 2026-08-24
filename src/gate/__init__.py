"""
GATE — Permission control, execution modes, audit log.

Single permission control point. Modes:
  plan     — Dry-run, show what would happen (no state change)
  ask      — Prompt user before each action
  manual   — User-triggered, batch mode
  auto     — Automatic, no user interaction (default)
  build    — Development/test mode, skip some checks
  troubleshoot — Verbose logging, detailed tracing
  yolo     — Absolute minimum checks (dangerous)

Audit log: hash-chained append-only record of all capability negotiation,
           BRAIN service calls, and model loading decisions. Each entry
           includes timestamp, caller, action, parameters (sanitized), result.

Capabilities are NOT providers. GATE decides which provider(s) can fulfill
each capability level, per request context.
"""
