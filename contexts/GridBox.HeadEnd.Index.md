# GridBox.HeadEnd Index

## Ownership

Company product context.

## Product Role

HeadEnd is the field-side communication layer of GridBox. Its responsibility is
bringing data from devices and meters in from the field safely and reliably.

## Core Rule

If the issue is before or during ingestion from field devices, it is probably
HeadEnd.

If the issue is after ingestion and is mainly about visualization, analytics,
customer-facing reporting, or billing interpretation, it is probably not
HeadEnd.

## Main Subcontexts

- `GridBox.HeadEnd.CoreDomains.md`
- `GridBox.HeadEnd.ApiAndServices.md`
- `GridBox.HeadEnd.Operations.md`
- `GridBox.HeadEnd.RoutingRules.md`
- `GridBox.HeadEnd.CommonIncidents.md`
- `GridBox.HeadEnd.Protocols.md`
- `GridBox.HeadEnd.ComponentMap.md`
- `GridBox.HeadEnd.CommonAnswerPatterns.md`
- `GridBox.HeadEnd.Sources.md`
- `GridBox.HeadEnd.Runbooks.md`
- `GridBox.HeadEnd.IncidentQuestions.md`
- `GridBox.MDM.md`

## Important Boundary

`MDM` is outside Sinan's direct responsibility. It may be mentioned frequently,
but should not automatically be treated as a HeadEnd issue.
