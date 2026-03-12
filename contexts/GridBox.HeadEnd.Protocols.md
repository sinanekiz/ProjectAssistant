# GridBox HeadEnd Protocols

## Purpose

This file explains the protocol-related portion of HeadEnd reasoning.

## Key Repository Signal

There is a dedicated protocol family under:

- `C:\Users\Sinan\source\repos\HayenTechnology\GridBox.Protocols`

and an explicit DLMS implementation under:

- `C:\Users\Sinan\source\repos\HayenTechnology\GridBox.Protocols\GridBox.Protocols.Dlms`

This means protocol interpretation is a real first-class concern in the
HeadEnd ecosystem.

## What This Means

If a message describes:

- command/result mismatch
- meter-read parsing issue
- vendor/device family inconsistency
- malformed or unexpected register/prepayment behavior

then protocol reasoning is likely relevant even before code lookup.

## Likely Protocol Topics

- DLMS communication
- register interpretation
- prepayment/token behavior
- meter object parsing
- device trace/reader behavior

## Likely Signs Of A Protocol Problem

- communication exists but values are wrong
- only one meter family is affected
- parser gets data but meaning is incorrect
- behavior changes with register/token/object type

## Likely Signs Of A Non-Protocol HeadEnd Problem

- no message left the queue
- workers are stalled globally
- all device families are failing the same way
- incident is clearly transport or infrastructure related

## Operational Guidance

When a message sounds protocol-specific:

1. Keep ownership under HeadEnd unless the symptom is clearly downstream-only.
2. Mention protocol/device-family suspicion explicitly.
3. Only inspect protocol repo code if the context is not enough to determine
   whether the behavior is expected.

## When Code Lookup Is Justified

- uncertainty between parser bug and expected protocol rule
- DLMS object/register semantics need confirmation
- device-family-specific incident requires implementation verification

## Current Known Focus

The repository structure strongly suggests DLMS is a major protocol area and
should be treated as one of the primary protocol contexts for HeadEnd support.
