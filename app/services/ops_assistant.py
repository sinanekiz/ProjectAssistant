from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import TeamsMessage
from app.services.setup_manager import is_setup_complete, test_database_connection


def answer_manual_question(question: str, db: Session | None = None) -> str:
    normalized = question.lower().strip()
    settings = get_settings()

    if not normalized:
        return "Bir soru yazarsan mevcut ayarlar, veritabani durumu veya Teams webhook testi hakkinda yardimci olabilirim."

    if any(token in normalized for token in ("db", "database", "veritabani", "postgres")):
        ok, message = test_database_connection(settings.database_url)
        return f"Veritabani durumu: {'hazir' if ok else 'baglanti sorunu var'}. Detay: {message}"

    if any(token in normalized for token in ("watch", "channel", "kanal")):
        channels = ", ".join(settings.watched_channels) or "Tanimli watched channel yok."
        return f"Izlenen kanallar: {channels}"

    if any(token in normalized for token in ("keyword", "anahtar", "kelime")):
        keywords = ", ".join(settings.relevance_keywords) or "Tanimli relevance keyword yok."
        return f"Relevance keyword listesi: {keywords}"

    if any(token in normalized for token in ("target", "sinan", "hedef")):
        return f"Hedef isim ayari: {settings.target_name}"

    if any(token in normalized for token in ("setup", "ayar", "kurulum")):
        return "Kurulum durumu hazir." if is_setup_complete() else "Kurulum henuz tamamlanmamis. Setup ekranindan gerekli alanlari doldurabilirsin."

    if any(token in normalized for token in ("teams", "webhook", "mesaj")):
        if db is None:
            return "Teams mesaj ozeti icin veritabani oturumu gerekli."
        count = db.scalar(select(func.count()).select_from(TeamsMessage)) or 0
        return f"Sistemde kayitli toplam Teams mesaji sayisi: {count}. Manuel test icin paneldeki JSON alanini kullanabilirsin."

    return (
        "Sun an su konularda yardimci olabilirim: veritabani durumu, watched channels, relevance keywords, hedef isim, kurulum durumu ve Teams webhook testi. "
        "Ornek soru: 'db durumu ne' veya 'watched channels ne?'"
    )
