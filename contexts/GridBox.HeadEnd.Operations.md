# GridBox.HeadEnd Operations

## Operational View

HeadEnd is likely run as a combination of:

- API host
- service hosts
- background workers
- queue consumers
- parser/listener components

## What To Ask First

When a HeadEnd issue arrives, first clarify:

1. Is the problem before ingestion or after ingestion?
2. Is the problem tied to a specific protocol or device family?
3. Is data missing, delayed, malformed, or duplicated?
4. Is command delivery failing or just the downstream display?

## Priority Guidance

Higher urgency examples:

- field communication stopped
- widespread meter/device connectivity failure
- parser failures blocking ingestion
- queue/worker backlog affecting live traffic
- command flow failure in production

Lower urgency examples:

- downstream reporting confusion
- historical display mismatch after data already arrived
- MDM-only interpretation issues
