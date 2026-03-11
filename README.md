# ProjectAssistant Sprint 5

Sprint 5, Telegram approval sonrasinda suggested reply'nin Microsoft Graph kullanilarak Teams'e geri gonderilmesini ekler.

## Bu sprintte ne var

- Telegram approval akisi (`polling` veya `webhook`)
- `approve` aksiyonunda Microsoft Graph uzerinden Teams delivery
- Chat ve channel destination resolution
- `sent_replies` tablosuna delivery sonucu kaydi
- Duplicate approve click icin idempotent koruma
- Delivery success/failure loglari

## Graph delivery akisi

1. Teams mesaji gelir ve `teams_messages` tablosuna yazilir.
2. Relevant ise triage sonucu olusur.
3. Telegram approval request gonderilir.
4. Kullanici `approve` verirse sistem approval kaydini kontrol eder.
5. Approval hala `pending` ise `approved` durumuna cekilir.
6. Ilgili `triage_result` ve `teams_message` yuklenir.
7. Mesaj metadata'sindan destination tipi belirlenir:
   - `conversation_type=chat` ise `chat_id` ile chat'e yeni mesaj gonderilir
   - `conversation_type=channel` ise `team_id`, `channel_id`, `parent_message_id` ile channel reply gonderilir
8. Sonuc `sent_replies` tablosuna yazilir.
9. Aynı approval tekrar gelirse ve delivery kaydi varsa ikinci kez gonderim yapilmaz.

## Beklenen Graph konfigurasyonu

```env
MICROSOFT_TENANT_ID=your-tenant-id
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret
MICROSOFT_GRAPH_BASE_URL=https://graph.microsoft.com/v1.0
```

## Beklenen Graph izinleri

Bu sprintte app-only client credentials modeli kullanilir. Pratikte Teams mesaj gonderimi icin Microsoft Graph tarafinda uygun uygulama izinlerine ihtiyacin olacak. Exact izin seti tenant politikasina ve destination tipine gore degisebilir.

Minimum beklenti:

- Teams message read icin Sprint 2'de kullandigin uygun Graph read izinleri
- Teams message send icin uygun Graph permission onayi

Not: Graph'in chat vs channel gonderim davranisi ve izin modeli her tenant'ta birebir ayni olmayabilir. Bu yuzden README ve adapter katmani pragmatik tutuldu; delegated/user-context send daha sonra temiz sekilde eklenebilir.

## Destination mapping

`teams_messages` artik delivery context icin su alanlari da tasir:

- `conversation_type`: `chat` veya `channel`
- `team_id`
- `channel_id`
- `chat_id`
- `parent_message_id`
- `thread_id`

Kullanim sekli:

- Chat mesaji ise `send_chat_message(chat_id, text)`
- Channel mesaji ise `reply_to_channel_message(team_id, channel_id, parent_message_id, text)`

## Known limitations

- Chat delivery, pragmatik olarak ayni chat'e yeni follow-up mesaj gonderir; true threaded reply modeli hedeflenmedi.
- Channel delivery icin Microsoft Graph reply endpoint kullanilir; ingestion sirasinda `team_id`, `channel_id`, `parent_message_id` saklanmis olmasi gerekir.
- Eger eski kayitlarda delivery context yoksa delivery `failed` olarak kaydedilir.
- Delivery basarisiz olduktan sonra duplicate approve retry otomatik re-send yapmaz; mevcut failed kayit korunur.

## Local test with mocks

Gercek Graph cagrisi olmadan test etmek icin testlerde `GraphClient.reply_to_channel_message` veya `GraphClient.send_chat_message` monkeypatch ediliyor.

Ornek yaklasim:

```python
monkeypatch.setattr(
    "app.adapters.graph_client.GraphClient.reply_to_channel_message",
    lambda self, **kwargs: GraphSendResult(success=True, message_id="graph-reply-1", destination_type="channel_reply"),
)
```

## Migration

Sprint 5 delivery context icin `teams_messages` tablosuna su kolonlari ekler:

- `conversation_type`
- `team_id`
- `chat_id`
- `parent_message_id`

Migration uygulama:

```bash
alembic upgrade head
```

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

## Ornek approve akisi

1. Telegram callback gelir:

```text
approve:12
```

2. Sistem `approval_requests.triage_result_id = 12` kaydini bulur.
3. Approval `pending` ise `approved` yapar.
4. `triage_results.message_id` uzerinden orijinal Teams mesaji yuklenir.
5. Mesaj `conversation_type=channel`, `team_id=team-42`, `channel_id=channel-99`, `parent_message_id=root-77` ise:

```text
POST /teams/team-42/channels/channel-99/messages/root-77/replies
```

6. Basarili olursa:
   - `sent_replies.delivery_status = sent`
   - callback cevabi harmless sekilde `sent` doner
7. Ayni approve tekrar gelirse ikinci kez gonderim yapilmaz.

## Notlar

- Teams bot SDK veya Bot Framework reply modeli kullanilmadi.
- Delivery yalnizca Microsoft Graph uzerinden yapilir.
- Jira, code analysis ve yeni kanal ekleme kapsam disidir.
