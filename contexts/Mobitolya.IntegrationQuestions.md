# Mobitolya Integration Questions

## Purpose

This file lists the minimum questions needed before deciding whether a
Mobitolya issue is really an integration bug or just a local workflow/data
problem.

## Minimum Questions

- Hangi entegrasyon etkileniyor
- Sorun veri gelmeme mi, veri gitmeme mi, gecikme mi, yoksa esleme sorunu mu
- Sorun tek siparis/urun/musteri kaydinda mi yoksa genel mi
- Son basarili calisma ne zamandi
- Mobitolya icinde beklenen veri hazir miydi

## Integration Families

Most likely families in this repo:

- Shopify
- Trendyol
- WooCommerce
- OpenCart
- marketplace/internal connector services
- messaging-related integrations

## Default Interpretation Rule

If the internal Mobitolya record itself is incomplete or invalid, do not treat
it as an integration failure first.

If the internal record looks correct but outbound/inbound sync is consistently
wrong, integration suspicion becomes stronger.

## Code Lookup Threshold

Only go to code when:

- the same integration fails repeatedly under valid input
- there is a repeatable mismatch in payload/state expectation
- context and operational checks no longer explain the issue
