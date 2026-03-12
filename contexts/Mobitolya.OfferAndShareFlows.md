# Mobitolya Offer And Share Flows

## Purpose

This file focuses on teklif, paylasim, yazdirma, PDF/WhatsApp gonderim ve buna
benziyen Mobitolya akislarini answer-first seviyede aciklar.

## Typical Questions

- Teklif neden gonderilmiyor
- WhatsApp paylasim neden acilmiyor
- PDF neden olusmadi
- Musteriye gittigini nasil anlarim
- Teklifte su alan neden boyle gorunuyor

## Default Reasoning Order

1. soru teklif olusturma mi, guncelleme mi, paylasma mi
2. sorun veri eksikligi mi, format mi, kanal acilamama mi
3. sorun tarayici/telefon davranisi mi, uygulama mantigi mi
4. ayni sorun herkeste mi yoksa tek kullanicida mi

## Non-Bug Explanations

Common non-code explanations:

- gerekli alanlar doldurulmamistir
- teklif kaydedilmeden share bekleniyordur
- cihazdaki WhatsApp/share hedefi kullanici tarafinda acilmamistir
- belge olusmus ama kullanici farkli yerden bakiyordur
- yazdirma/goruntuleme tarayici kisitina takiliyordur

## Bug Suspicion Signals

Code lookup becomes more likely when:

- ayni veriyle tekrarli olarak share hic olusmuyorsa
- belirli bir belge tipi sistematik olarak bozuk cikiyorsa
- tekil kullanici degil, ayni rol/kullanicilar toplu etkileniyorsa
- kayitli veri ile ekranda gorunen veri tutarsizsa

## Routing Rule

Offer/share sorulari once bu baglamdan cevaplanmali; bunlar hemen entegrasyon
veya backend bug'i gibi ele alinmamali.
