# GridBox MDM Boundary

## Purpose

This file exists to protect ownership boundaries between HeadEnd and MDM.

## Ownership Rule

MDM is not Sinan's primary responsibility.

Questions about MDM may appear frequently in messages, but they should not be
treated as HeadEnd issues unless the real problem is clearly upstream in field
data acquisition.

## MDM Role

MDM is the downstream layer that uses field data for:

- visualization
- analysis
- customer-facing interpretation
- reporting
- billing-related downstream flows

## HeadEnd Role

HeadEnd is responsible for:

- obtaining field data from devices/meters
- safe and reliable communication
- ingestion/transport/parsing on the field side

## Routing Rule

If the problem is:

- before data enters the platform from field devices -> likely HeadEnd
- after data is already collected and the issue is about use/presentation of
  that data -> likely MDM or another downstream team

## Mixed Cases

Some incidents may mention MDM while actually being HeadEnd issues, for example:

- MDM screen is empty because HeadEnd never received field data
- downstream system cannot find data because ingestion failed upstream

In such cases, the assistant should identify upstream failure as the real issue.

## Why This Context Matters

Messages that mention MDM should not automatically pull the assistant away from
HeadEnd ownership reasoning. The assistant must first determine whether the
problem is upstream field communication or downstream data usage.
