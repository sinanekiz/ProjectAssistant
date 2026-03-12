# Mobitolya Common Answer Patterns

## Purpose

This file defines the preferred answer pattern for normal Mobitolya support
traffic.

## Default Pattern

When a Mobitolya message arrives, answer in this order:

1. identify the business area
2. explain the most likely non-bug cause
3. give the user the next practical step
4. only suggest technical investigation if the issue still looks abnormal

## Good Default Phrases

### Operational Guidance

- This looks more like a workflow or data prerequisite issue than a confirmed bug.
- First check whether the relevant customer, document, or contact data exists.
- This screen usually depends on the selected account, record, date range, or branch.

### Share and Messaging Guidance

- If the share action failed, the first thing to verify is the target record and contact data.
- WhatsApp-related actions usually depend on the selected customer and shareable record state.

### Automation Guidance

- If you expected this to happen automatically, the likely causes are queue timing, parser expectation, or missing required input.
- This sounds like an automation expectation mismatch before it sounds like a real defect.

### Bug Escalation Guidance

- If the same steps are reproducible and the expected prerequisites are present, then this may be a real bug.
- If multiple users see the same breakage on the same screen, code or logs become worth checking.

## What To Avoid

- Do not over-explain technical architecture for simple WhatsApp support questions.
- Do not default to code inspection for every "why didn't it work" message.
- Do not mix Mobitolya answers with GridBox or HeadEnd reasoning.
