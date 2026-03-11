# ProjectAssistant

ProjectAssistant, Sinan icin Teams mesajlarini Microsoft Graph uzerinden dinleyen, AI triage yapan, Telegram uzerinden onay isteyen ve onaylanan yanitlari tekrar Teams'e gonderebilen moduler bir FastAPI uygulamasidir.

## Yeni panel akisi

- `/console`: sadece son gelen mesajlar ve son loglar
- `/settings/general`: genel uygulama, panel auth ve Telegram ayarlari
- `/settings/teams`: Microsoft Graph Teams/chat ayarlari, chatleri cekme, abonelik ve label duzenleme

## Ayar saklama modeli

Artik environment tarafinda yalnizca `DATABASE_URL` tutulur.
Diger tum ayarlar veritabanindaki `app_settings` tablosunda key/value olarak saklanir.

`.env.example`:

```env
DATABASE_URL=postgresql+psycopg://projectassistant:projectassistant@db:5432/projectassistant
```

## Migration

Yeni migration:
- `20260311_0004_app_settings.py`

Uygulamak icin:

```bash
alembic upgrade head
```

## Render notu

Render environment variables icinde en az su alan olmalidir:

```env
DATABASE_URL=postgresql+psycopg://...
```

Uygulama ayaga kalkinca diger ayarlari panelden kaydedebilirsin.

## Teams ayarlari

`/settings/teams` ekraninda:
- Microsoft Graph tenant/client/secret bilgilerini gir
- `MICROSOFT_USER_ID` alanina kendi Entra kullanici object id degerini yaz
- `Chatleri Cek` ile kullanici chatlerini manuel olarak getir
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
5. approve verilirse delivery Microsoft Graph ile Teams'e gonderilir
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

- `GET /users/{id}/chats` Graph tarafinda tenant'a gore degisebilir; bu nedenle Teams ayarlarinda manuel chat link/id fallback'i vardir.
- Chat delivery pragmatik olarak ayni chat'e yeni follow-up message gonderir.
- Channel delivery Microsoft Graph reply endpoint uzerinden calisir.
- Abonelik sureleri dolarsa yenilenmeleri gerekir.
