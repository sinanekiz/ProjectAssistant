# Mobitolya Accounting Answer Patterns

## Purpose

This file standardizes how finance/accounting/document questions should be
answered before jumping to implementation detail.

## Typical Topics

- cari hareket neden boyle gorunuyor
- hesap ekstresi neden cikmiyor
- belge neden olusmadi
- borc/alacak niye tutmuyor gibi gorunuyor
- tahsilat veya odeme kaydi nasil kontrol edilir

## Default Answer Pattern

1. hangi ekran veya belge tipi oldugunu netlestir
2. beklenen sonuc ile gorulen sonucu ayir
3. veri eksikligi mi, filtreleme mi, durum mantigi mi diye ayir
4. ayni durum tek kayitta mi yoksa genel mi bak

## Good Default Framing

- Bu durum once finansal hareketin gercekten olusup olusmadigi acisindan kontrol edilmeli.
- Once belge kaydi var mi, sonra ekranda dogru filtre ile mi bakiliyor diye ayirmak gerekir.
- Bu tip sorularin bir kismi hata degil, muhasebe akisinin durum farkindan kaynaklanir.

## Bug Suspicion Signals

- kayit olusuyor ama ekranlar arasi tutarsizlik var
- ayni tur belgede sistematik sapma var
- toplamlar tekrarlanabilir sekilde yanlis hesaplaniyor
- export/print ile ekran ayni sonucu vermiyor

## Out Of Scope Rule

If the question is really payment gateway, e-invoice provider, or external
accounting integration behavior, route toward integration context after basic
screen/data checks.
