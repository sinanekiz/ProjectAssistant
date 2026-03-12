# GridBox HeadEnd Incident Questions

## Purpose

This file gives the shortest useful question set for understanding whether an
incoming HeadEnd report is a real issue, an environment issue, or a downstream
misrouting.

## Minimum Questions

### Scope

- Tek cihaz mi etkileniyor, bir cihaz grubu mu, yoksa genel mi
- Sorun ne zamandan beri var
- Daha once calisiyordu da sonradan mi bozuldu

### Symptom Type

- Veri hic mi gelmiyor, gec mi geliyor, yoksa yanlis mi geliyor
- Komut hic mi gitmiyor, gec mi gidiyor, yoksa reddediliyor mu
- Sorun sadece belirli cihaz/protokol/vendor grubunda mi

### Boundary Check

- Veri HeadEnd tarafina hic ulasmiyor mu
- Veri ulasiyor ama MDM veya rapor tarafinda mi gorunmuyor
- Sikayet aslinda gorsellestirme/faturalama konusu mu

### Repro/Pattern

- Tekil olay mi yoksa tekrar eden bir pattern mi
- Belirli saatlerde mi oluyor
- Belirli bir saha, bayi, lokasyon veya toplu islemle mi baglantili

## Interpretation Rule

If these questions already point clearly to ownership and likely layer, answer
from context. If the answers still leave behavior ambiguous, then code lookup is
justified.
