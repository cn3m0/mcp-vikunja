# Task 52 - NanoPi Private-Host Profile

## Context

Date: 2026-03-02  
Related task: `http://127.0.0.1:3456/tasks/52`

Goal:
- Define how NanoPi private hosting differs from VPS baseline and what to prepare.

## NanoPi Profile Characteristics

Pros:
- Full private control.
- Low power consumption.
- No monthly cloud compute bill.

Constraints:
- Dependent on home power and internet.
- Typically lower CPU/RAM/storage throughput than VPS.
- More responsibility for hardware maintenance and failover.

## Required Preparation

1. Hardware and OS
- Stable power supply.
- Reliable storage (prefer SSD over SD card when possible).
- 64-bit Linux image with security updates enabled.

2. Network design
- Static DHCP lease or fixed IP.
- Router port-forwarding only if remote access is required.
- Prefer VPN/Tailscale/WireGuard over broad public exposure.

3. Runtime stack
- Install Docker + Compose.
- Use same repository and compose layout as PC/VPS baseline.
- Keep environment variables aligned with production profile.

4. Reliability controls
- Auto-restart services (`unless-stopped`).
- Scheduled backups to external location.
- UPS recommended for power outage tolerance.

## Migration Delta vs VPS

Differences to account for:
- Public TLS termination may stay on router/VPN edge instead of direct host ingress.
- Bandwidth and latency depend on home ISP.
- Recovery process must include hardware-level failures.

Same core flow:
- `docker compose up -d --build`
- `make verify`
- `make test-mcp`

## Acceptance Criteria

- NanoPi host can run full stack stably for normal workload.
- Backup and restore tested.
- Remote management path documented and secured.
