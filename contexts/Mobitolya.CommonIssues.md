# Mobitolya Common Issues

## Purpose

This file captures the most likely non-code-first explanations for common
Mobitolya support traffic.

## Core Rule

Most Mobitolya support questions should be treated as workflow, data,
configuration, or integration-state issues before treating them as confirmed
software defects.

## Common Issue Buckets

### Offer and Share Issues

Typical signals:

- offer exists but cannot be shared
- WhatsApp share opens incorrectly
- customer target is wrong or missing
- generated share text is incomplete

Likely first checks:

- customer phone/contact completeness
- whether the selected record is the intended offer
- whether the share action belongs to the right screen/state

### Accounting and Statement Issues

Typical signals:

- balance looks wrong
- statement share is missing
- receivable visibility is confusing
- document totals seem unexpected

Likely first checks:

- date filters
- selected account/customer
- whether the user expects accounting result versus raw operational record
- whether the issue belongs to document generation or statement display

### Order Intake and Parsing Issues

Typical signals:

- incoming order not created
- parsed fields are wrong
- automation skipped a request
- request came in but system did nothing

Likely first checks:

- source channel and format
- parser expectation mismatch
- worker/queue lag
- incomplete payload or unsupported wording

### Inventory and Warehouse Issues

Typical signals:

- stock not visible
- quantity mismatch
- expected movement missing
- production/warehouse state confusion

Likely first checks:

- selected branch/depot
- item variant or product mapping
- whether the user is looking at summary versus movement detail

### Marketplace and Store Integration Issues

Typical signals:

- product sync not happening
- order not imported
- status not reflected back
- external marketplace data differs from Mobitolya

Likely first checks:

- integration-specific state
- credential/connectivity status
- queue timing
- mapping mismatch between systems

### Messaging and Notification Issues

Typical signals:

- message did not go out
- reminder was not sent
- wrong recipient or wrong text
- expected automation output missing

Likely first checks:

- contact data
- template/source record
- queue/worker state
- channel-specific restrictions

## Response Strategy

When a question arrives:

1. Identify the functional domain.
2. Decide if the issue sounds like:
   - normal workflow confusion
   - missing data/prerequisite
   - integration/queue delay
   - probable real bug
3. Answer from process context first.
4. Only escalate to code lookup if behavior still does not make sense.

## Signs It Might Be A Real Bug

- same steps worked before and now fail consistently
- multiple users report the same breakage
- wrong record is changed or shown
- automation behaves inconsistently with the same input
- a screen action claims success but produces no downstream result

## Signs It Is Probably Not A Bug

- user is unsure which screen or record they are using
- required customer/contact/document data is missing
- issue is limited to one malformed input
- expectation sounds like a feature request rather than broken behavior

## Escalation Threshold

If a question cannot be resolved confidently from these issue patterns, the
assistant may inspect code or logs to confirm whether the reported behavior is a
real product defect.
