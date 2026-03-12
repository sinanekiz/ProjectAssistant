# GridBox.HeadEnd Routing Rules

## Route To HeadEnd When

- message is about field devices or meters
- message is about communication, listeners, queues, protocols, or parsers
- message says data never arrived from the field
- message says commands are not reaching devices

## Route Away From HeadEnd When

- issue is mainly analytics, reporting, dashboards, or billing after ingestion
- message is clearly about MDM-facing business interpretation
- customer-facing visualization is broken but field ingestion succeeded

## Borderline Rule

If uncertain, ask whether the data failed before ingestion or after ingestion.

- before ingestion -> HeadEnd
- after ingestion -> likely MDM/downstream
