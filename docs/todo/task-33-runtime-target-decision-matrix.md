# Task 33 - Runtime Target Decision Matrix (VPS vs NAS vs Mini-PC)

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

## Recommendation

Recommended target:
- Run the core stack (`vikunja`, `db`, `mcp-adapter`) on a VPS as baseline.

Optional hybrid later:
- Keep local worker execution (tmux/deep work) on PC when needed, but keep task system and MCP endpoint always-on in VPS.

Rationale:
- Best fit for the requirement that work must continue while personal hardware is offline.
- Simplifies collaboration across multiple Codex sessions and devices.

## Proposed Next Steps

1. Confirm runtime choice: VPS baseline.
2. Execute `Task #34` (minimal infrastructure baseline):
   - reverse proxy with TLS
   - Docker restart policies
   - health checks
   - backup schedule for PostgreSQL and config
3. Define RTO/RPO targets:
   - RTO: 15 minutes
   - RPO: 24 hours (minimum baseline)
4. Add monitoring + alerting (`Task #46`) after baseline deploy.

## Decision Status

- Status: `Proposed`
- Owner: project maintainers
- Pending confirmation: yes
