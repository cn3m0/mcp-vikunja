# Task 33 - Runtime Strategy Decision (Phased Rollout)

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/33`

Primary requirement:
- The MCP/Vikunja workflow must remain available even when the main laptop/PC is sleeping, shut down, or disconnected.

## Decision Criteria

Weights:
- Availability/Uptime: 35%
- Operational effort: 20%
- Failure recovery speed: 15%
- Security/exposure control: 15%
- Cost (monthly): 15%

Scoring scale:
- `1` = weak
- `3` = acceptable
- `5` = strong

## Option Comparison

| Option | Availability (35) | Ops Effort (20) | Recovery (15) | Security (15) | Cost (15) | Weighted Score |
|---|---:|---:|---:|---:|---:|---:|
| VPS (cloud) | 5 | 4 | 4 | 4 | 3 | 4.20 |
| NAS (self-hosted at home) | 3 | 3 | 2 | 3 | 4 | 3.00 |
| Mini-PC (self-hosted at home) | 3 | 3 | 2 | 3 | 4 | 3.00 |

Interpretation:
- VPS is the strongest default for continuity and remote access.
- NAS and Mini-PC can work, but both depend on home power/network stability and local maintenance.

## Impact of Sleep/Offline Scenarios

| Scenario | VPS | NAS | Mini-PC |
|---|---|---|---|
| Main laptop sleeps | No impact | No impact | No impact |
| Home power outage | No impact | Service down | Service down |
| Home internet outage | No impact | Service unreachable remotely | Service unreachable remotely |
| Router reboot | No impact | Temporary downtime | Temporary downtime |
| Host hardware reboot | Managed restart policy | Manual intervention more likely | Manual intervention more likely |

## Decision

Confirmed rollout strategy:

1. Phase A (now): develop on the current PC.
2. Phase B (short-term optional): move to a dedicated always-on Codex PC.
3. Phase C (long-term): run production on VPS and/or private NanoPi hosting.

Rationale:
- Keeps current development speed high (no migration blocker now).
- Adds an immediate always-on path when dedicated hardware is ready.
- Preserves long-term goal of stable external availability via VPS and private-host flexibility via NanoPi.

## Execution Consequences

1. `Task #34` must define a baseline for all three phases, not only VPS.
2. Backup/restore and health checks should be implemented already in Phase A.
3. Migration artifacts must be prepared so Phase B/C can be executed without redesign.

## Next Steps

1. Execute `Task #34` with profile-based baseline (PC, Codex box, VPS/NanoPi).
2. Break down into small operational tasks under `To-Do`.
3. Keep `Task #32` open until Phase A baseline is fully validated.

## Decision Status

- Status: `Confirmed`
- Owner: project maintainers
- Pending confirmation: no
