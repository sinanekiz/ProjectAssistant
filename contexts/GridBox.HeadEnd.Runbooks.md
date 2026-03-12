# GridBox HeadEnd Runbooks

## Purpose

This file defines the default operational runbook order for common HeadEnd-side
support and incident handling.

## Standard Runbook Order

1. confirm ownership is really HeadEnd
2. determine whether the issue is device-specific, site-specific, or broad
3. determine whether the problem is transport, processing, or interpretation
4. determine whether data is missing, delayed, duplicated, or malformed
5. only then decide whether code lookup is necessary

## Common Runbook Lenses

### Missing Data

Check in this order:

1. does the field device appear reachable at all
2. is the expected communication window still open
3. is there queue or worker delay after ingestion
4. is data present but not visible in the expected downstream place

### Command Problems

Check in this order:

1. was the command created
2. was it dispatched to the correct device/site path
3. did the command remain queued or retrying
4. did the field side acknowledge or reject it

### Wrong Values

Check in this order:

1. did the raw payload arrive
2. is the wrongness protocol-specific or device-family-specific
3. is parser interpretation likely wrong
4. is the complaint actually downstream formatting rather than ingestion

### Slow Processing

Check in this order:

1. queue backlog
2. worker lag
3. cache/state visibility mismatch
4. broad infrastructure issue

## Escalation Rule

If the runbook explains the situation with ownership, state, or operations, do
not immediately fall back to code lookup. Use code only when the runbook no
longer explains observed behavior.
