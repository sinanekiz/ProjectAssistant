# GridBox HeadEnd Common Incidents

## Purpose

This file captures the typical incident patterns for GridBox HeadEnd so the
assistant can classify problems before reading code.

## Core Rule

HeadEnd owns secure and reliable field communication. If the problem is about
collecting, transporting, parsing, or handling field-device communication, it
is likely a HeadEnd concern.

## Common Incident Buckets

### Data Not Arriving From Field

Typical signals:

- meter data missing
- no new reads for a device group
- field data stopped after a specific point in time

Likely first checks:

- field communication status
- queue/consumer lag
- parser failure suspicion
- device-side or network-side outage

### Command Not Reaching Device

Typical signals:

- remote command not executed
- request created but no device response
- retry behavior unclear

Likely first checks:

- whether the command left HeadEnd
- transport/protocol pathway
- device availability
- command lifecycle visibility

### Queue or Worker Backlog

Typical signals:

- messages visible but not processed
- delayed device updates
- workers appear alive but output is stale

Likely first checks:

- worker health
- queue backlog
- stuck consumer or parser stage

### Parser or Protocol Interpretation Problem

Typical signals:

- raw communication exists but values are wrong
- meter response cannot be interpreted
- one vendor/device family fails while others work

Likely first checks:

- protocol family
- parser stage
- device-specific mapping
- whether the issue belongs to protocol implementation rather than transport

### Device-Specific or Vendor-Specific Behavior

Typical signals:

- only one meter family has the issue
- behavior differs by firmware/vendor/device type
- expected field action succeeds elsewhere but not on a specific family

Likely first checks:

- protocol support
- known device constraints
- vendor-specific handling path

## Incident Handling Pattern

When a HeadEnd issue arrives:

1. Decide whether the issue is pre-ingestion, in-ingestion, or post-ingestion.
2. If it is pre- or in-ingestion, keep it in HeadEnd scope.
3. If it is post-ingestion and mainly customer-facing analytics/reporting, route
   toward MDM or downstream teams.
4. Use code lookup only after a likely layer is identified.

## Strong Signals It Is Not HeadEnd

- issue is only in dashboards or customer-facing reports
- data arrived but interpretation, billing, or visualization is wrong
- the complaint is mainly about post-processing, not field transport

## When Repo Lookup Is Worthwhile

Use repository inspection when:

- a real regression is suspected
- queue behavior is unclear
- a parser/protocol bug is plausible
- incident ownership between HeadEnd and another system remains uncertain
