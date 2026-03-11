# ProjectAssistant

ProjectAssistant, Sinan icin Teams mesajlarini Microsoft Graph uzerinden dinleyen, AI triage yapan, Telegram uzerinden onay isteyen ve onaylanan yanitlari Sinan'in Microsoft hesabi olarak tekrar Teams'e gonderebilen moduler bir FastAPI uygulamasidir.

## Panel akisi

- `/console`: sadece son gelen mesajlar ve son loglar
- `/settings/general`: genel uygulama, panel auth ve Telegram ayarlari
- `/settings/teams`: Microsoft Graph Teams/chat ayarlari, Microsoft hesabini baglama, chat abonelikleri ve label duzenleme

## Ayar saklama modeli

Environment tarafinda yalnizca `DATABASE_URL` tutulur.
Diger tum ayarlar veritabanindaki `app_settings` tablosunda key/value olarak saklanir.

`.env.example`:

```env
DATABASE_URL=postgresql+psycopg://projectassistant:projectassistant@db:5432/projectassistant
```

## Migration

Yeni migrationlar:
- `20260311_0004_app_settings.py`
- `20260311_0005_seed_panel_auth.py`

Uygulamak icin:

```bash
alembic upgrade head
```

## Varsayilan panel girisi

Ilk kurulumdan sonra panel icin varsayilan bilgiler DB'ye seed edilir:

- kullanici adi: `sekiz`
- sifre: `qasx7865`

Bunlari daha sonra `/settings/general` ekranindan degistirebilirsin.

## Render notu

Render environment variables icinde en az su alan olmalidir:

```env
DATABASE_URL=postgresql+psycopg://...
```

Uygulama ayaga kalkinca diger ayarlari panelden kaydedebilirsin.

## Microsoft hesabini baglama

Teams chat listesini gorebilmek ve approve sonrasi mesaji Sinan'in hesabi olarak gonderebilmek icin `/settings/teams` ekranindaki `Microsoft Hesabimi Bagla` butonu kullanilir.

Bu akisin calismasi icin Azure App Registration icinde redirect URI olarak su adresi eklenmelidir:

```text
https://YOUR_HOST/auth/microsoft/callback
```

Render kullaniyorsan ornek:

```text
https://projectassistant.onrender.com/auth/microsoft/callback
```

Delegated login sonrasi uygulama refresh token'i DB'de saklar ve Graph delivery icin bunu kullanir.

## Teams ayarlari

`/settings/teams` ekraninda:
- Microsoft Graph tenant/client/secret bilgilerini gir
- `Microsoft Hesabimi Bagla` ile delegated auth akisini tamamla
- `Chatleri Cek` ile kendi chatlerini `/me/chats` uzerinden getir
- Teams web chat linki veya `19:...@thread.v2` id ile manuel chat ekleyebilirsin
- `Secili Chatlere Abone Ol` ile Graph subscription olusturulur
- mevcut aboneliklerin label'larini ayni ekranda degistirebilirsin

## Genel ayarlar

`/settings/general` ekraninda:
- panel login username/password/session secret
- Telegram bot token ve chat id
- Telegram approval mode (`polling` / `webhook`)
- `PUBLIC_WEBHOOK_BASE_URL`
- OpenAI API key

Ayni ekranda Telegram webhook icin iki tus vardir:
- `Webhooku Aktif Et`
- `Webhooku Kapat`

Bu, polling ve webhook cakismasini yonetmek icin eklendi.

## Graph webhook

Webhook endpoint:

```text
POST /webhooks/graph
```

Validation request ornegi:

```bash
curl -X POST "https://your-host/webhooks/graph?validationToken=abc123"
```

Beklenen cevap:

```text
abc123
```

## Telegram approval akisi

1. Relevant Teams/chat mesaji gelir
2. mesaj normalize edilip `teams_messages` tablosuna yazilir
3. triage olusur
4. Telegram approval request gonderilir
5. approve verilirse delivery delegated Microsoft Graph token ile Teams'e gonderilir
6. sonuc `sent_replies` tablosuna yazilir

## Local calistirma

```bash
copy .env.example .env
docker compose up --build
```

veya

```bash
copy .env.example .env
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

## Known limitations

- App-only Graph token ile chat send kullanilmaz; delivery icin delegated login gerekir.
- `Chatleri Cek` `/me/chats` kullanir; delegated login olmadan chat listesi gelmez.
- Chat delivery pragmatik olarak ayni chat'e yeni follow-up message gonderir.
- Channel delivery Microsoft Graph reply endpoint uzerinden delegated token ile calisir.
- Abonelik sureleri dolarsa yenilenmeleri gerekir.
