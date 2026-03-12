# Mobitolya Screen Map

## Purpose

This file maps the visible Mobitolya functional screens and pages to support
question domains.

## Main App Areas

### Offer

Frontend area:

- `mobitolya.web\src\pages\App\Offer`

Key screens/files:

- `OfferTable.vue`
- `OfferEdit.vue`
- `OfferView.vue`
- `OfferPrint.vue`

Use this area for:

- teklif olusturma
- teklif gonderme
- WhatsApp share issues
- teklif goruntuleme/duzenleme

### Accounting

Frontend area:

- `mobitolya.web\src\pages\App\Accounting`

Representative screens/files:

- `Accounting.vue`
- `FinancialAccountTable.vue`
- `FinancialAccountStatement.vue`
- `FinancialDocumentIndex.vue`
- `FinancialDocumentTable.vue`
- `Statement.vue`

Use this area for:

- hesap ekstresi
- cari hareketler
- borc/alacak gorunumu
- finansal belge olusturma/goruntuleme
- statement share flows

### Order

Frontend area:

- `mobitolya.web\src\pages\App\Order`

Use this area for:

- siparis alma
- siparis durumu
- siparis parse/otomasyon sorulari

### Product

Frontend area:

- `mobitolya.web\src\pages\App\Product`

Use this area for:

- urun kartlari
- urun varyantlari
- urun bilgisi duzenleme

### Warehouse

Frontend area:

- `mobitolya.web\src\pages\App\Warehouse`

Use this area for:

- stok
- depo hareketleri
- stok uygunluk ve gorunurluk

### Production

Frontend area:

- `mobitolya.web\src\pages\App\Production`

Use this area for:

- uretim akisleri
- uretim durum ve takibi

### Statistics

Frontend area:

- `mobitolya.web\src\pages\App\Statistics`

Use this area for:

- ozet ekranlar
- rapor ve durum goruntuleme

### Invoice, MailSms, SalesChannel, Company, Address, User

Other visible domains under App pages.

Use these for:

- fatura akislarina bagli ekranlar
- mail/sms bildirim davranislari
- satis kanali ve entegrasyon ekranlari
- firma/adres/kullanici ayarlari

## Routing Rule

If a support question clearly names or implies a visible screen, answer from the
screen/domain context first instead of treating it as a generic backend issue.
