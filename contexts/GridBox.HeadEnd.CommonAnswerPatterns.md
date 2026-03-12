# GridBox HeadEnd Common Answer Patterns

## Purpose

This file defines the default response style and reasoning pattern for common
HeadEnd support and incident questions.

## Default Pattern

When a HeadEnd question arrives, structure the answer as:

1. likely ownership
2. likely layer
3. likely first checks
4. whether code lookup is needed

## Good Default Phrases

### Ownership Clarification

- This sounds like a HeadEnd-side issue because it affects field ingestion or device communication.
- This sounds downstream of HeadEnd because the complaint starts after data is already collected.
- This may mention MDM, but the real failure still looks upstream in HeadEnd.

### Incident Triage

- First we should determine whether the data never arrived, arrived late, or arrived but was interpreted incorrectly.
- This sounds more like a queue/worker/consumer delay than a field-device outage.
- This sounds more like a parser or protocol interpretation issue than a transport issue.

### Protocol-Specific Framing

- If the raw communication exists but the value is wrong, protocol or parser behavior becomes a stronger suspect.
- If only one device family is affected, this increases the likelihood of a protocol-specific path.

### Escalation Guidance

- If the same pattern is reproducible and not explained by context, then code inspection is justified.
- If this is only a reporting or visualization problem after ingestion, it should likely be routed away from HeadEnd.

## What To Avoid

- Do not jump straight into code-level explanation unless runtime behavior is truly unclear.
- Do not treat every missing-data complaint as a parser bug.
- Do not absorb MDM ownership just because the message mentions MDM.
