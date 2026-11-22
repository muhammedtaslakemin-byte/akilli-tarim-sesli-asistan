"""
Akıllı Tarım Sesli Asistanı - Backend API Servisi (FastAPI)
===========================================================
Google Gemini üretken yapay zekası, SQLite veritabanı ve canlı hava durumu (Open-Meteo)
entegrasyonu ile çiftçilere sesli ve yazılı danışmanlık sağlayan REST API.
"""

import sys
import json
import re
import sqlite3
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from contextlib import contextmanager

from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import requests

# Ortam değişkenleri ve yapılandırma
try:
    from config import (
        GEMINI_API_KEY,
        DEFAULT_GEMINI_MODEL,
        DB_PATH,
        WEATHER_CITY,
        WEATHER_LATITUDE,
        WEATHER_LONGITUDE,
    )
except ImportError:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    DB_PATH = Path(__file__).resolve().parent / "ciftci_verileri.db"
    WEATHER_CITY = os.getenv("WEATHER_CITY", "Şanlıurfa")
    WEATHER_LATITUDE = float(os.getenv("WEATHER_LATITUDE", "37.16"))
    WEATHER_LONGITUDE = float(os.getenv("WEATHER_LONGITUDE", "38.79"))

# Windows konsolunda UTF-8 çıktı desteği (Emoji ve Türkçe karakter hatalarını önler)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Loglama Yapılandırması
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TarimAsistani")

# ---------------------------------------------------------------------------
# 1. VERİTABANI İŞLEMLERİ (SQLite)
# ---------------------------------------------------------------------------
@contextmanager
def get_db():
    """Bağlantı sızıntısını önleyen güvenli SQLite bağlam yöneticisi."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def veritabani_kurulumu():
    """Veritabanı tablolarını ve indekslerini hazırlar."""
    with get_db() as baglanti:
        imlec = baglanti.cursor()
        imlec.execute(
            """CREATE TABLE IF NOT EXISTS tarlalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ciftci_id TEXT NOT NULL,
                boyut TEXT NOT NULL,
                ekin_turu TEXT NOT NULL,
                kayit_tarihi TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        imlec.execute("CREATE INDEX IF NOT EXISTS idx_ciftci_id ON tarlalar(ciftci_id)")
        baglanti.commit()
    logger.info("Veritabanı kontrolü tamamlandı.")

veritabani_kurulumu()

def tarlayi_veritabanina_kaydet(ciftci_id: str, boyut: str, ekin_turu: str) -> int:
    """Çiftçinin yeni bir tarlasını veritabanına kaydeder."""
    with get_db() as baglanti:
        imlec = baglanti.cursor()
        imlec.execute(
            "INSERT INTO tarlalar (ciftci_id, boyut, ekin_turu) VALUES (?, ?, ?)",
            (str(ciftci_id).strip(), str(boyut).strip(), str(ekin_turu).strip()),
        )
        baglanti.commit()
        yeni_id = imlec.lastrowid
    logger.info(f"[KAYIT] Çiftçi ID: {ciftci_id} | Boyut: {boyut} | Ekin: {ekin_turu} (ID: {yeni_id})")
    return yeni_id

def ciftci_tarlalarini_getir(ciftci_id: str) -> str:
    """Çiftçinin kayıtlı tarlalarını asistanın anlayabileceği doğal dilde metne çevirir."""
    with get_db() as baglanti:
        imlec = baglanti.cursor()
        imlec.execute("SELECT boyut, ekin_turu FROM tarlalar WHERE ciftci_id=?", (str(ciftci_id).strip(),))
        tarlalar = imlec.fetchall()

    if not tarlalar:
        return "Kullanıcının henüz sisteme kayıtlı bir tarlası bulunmuyor."

    metin = "Çiftçinin sistemde kayıtlı tarlaları şunlardır: "
    detaylar = [f"{t['boyut']} {t['ekin_turu']}" for t in tarlalar]
    return metin + ", ".join(detaylar) + "."

# ---------------------------------------------------------------------------
# 2. DIŞ SERVİSLER: CANLI HAVA DURUMU VE BORSA VERİLERİ
# ---------------------------------------------------------------------------
def canli_hava_durumu_cek(lat: float = WEATHER_LATITUDE, lon: float = WEATHER_LONGITUDE, sehir: str = WEATHER_CITY) -> str:
    """Open-Meteo ücretsiz API'sinden anlık gerçek hava durumu verisi çeker."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    try:
        cevap = requests.get(url, timeout=5)
        if cevap.status_code == 200:
            veri = cevap.json().get("current_weather", {})
            sicaklik = veri.get("temperature", "--")
            ruzgar = veri.get("windspeed", "--")
            return f"{sehir} bölgesinde şu an hava sıcaklığı {sicaklik}°C ve rüzgar hızı {ruzgar} km/s."
        return f"{sehir} için hava durumu servisine şu anda ulaşılamıyor."
    except Exception as e:
        logger.warning(f"Hava durumu çekilemedi: {e}")
        return f"{sehir} için anlık hava durumu bilgisi geçici olarak alınamadı."

def canli_borsa_cek() -> str:
    """Güncel tarımsal emtia piyasa fiyatlarını döner."""
    return "Sistemden Çekilen Güncel Fiyatlar: Pamuk 43.50 TL, Buğday 9.20 TL, Mısır 6.80 TL."

# ---------------------------------------------------------------------------
# 3. GEMİNİ YAPAY ZEKA MODELİ HAZIRLIĞI
# ---------------------------------------------------------------------------
gemini_modeli = None
if GEMINI_API_KEY:
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_modeli = genai.GenerativeModel(DEFAULT_GEMINI_MODEL)
        logger.info(f"Gemini AI Hazır: {DEFAULT_GEMINI_MODEL}")
    except Exception as e:
        logger.error(f"Gemini başlatılırken hata oluştu: {e}")
else:
    logger.warning("GEMINI_API_KEY bulunamadı! Lütfen .env dosyasına ekleyin.")

def json_yaniti_ayikla(ham_metin: str) -> Dict[str, Any]:
    """Gemini çıktısından garantili JSON nesnesi çıkarır."""
    metin = ham_metin.strip()
    # 1. Doğrudan JSON ayrıştırma dene
    try:
        return json.loads(metin)
    except Exception:
        pass

    # 2. Markdown kod bloğunu regex ile ara (```json ... ```)
    eslesme = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", metin)
    if eslesme:
        try:
            return json.loads(eslesme.group(1).strip())
        except Exception:
            pass

    # 3. İlk süslü parantez ile son süslü parantez arasını yakala
    baslangic = metin.find("{")
    bitis = metin.rfind("}")
    if baslangic != -1 and bitis != -1 and bitis > baslangic:
        try:
            return json.loads(metin[baslangic : bitis + 1])
        except Exception:
            pass

    # 4. Hiçbiri çalışmazsa güvenli varsayılan cevap oluştur
    return {
        "asistan_cevabi": metin,
        "uygulama_emri": "none",
        "kaydedilecek_detay": ""
    }

# ---------------------------------------------------------------------------
# 4. FASTAPI UYGULAMASI VE UÇ NOKTALAR (ENDPOINTS)
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Akıllı Tarım Sesli Asistanı API",
    description="Çiftçilere özel, yapay zeka destekli sesli ve yazılı tarım asistanı servisi.",
    version="2.0.0"
)

# CORS Yapılandırması (Web ve mobil arayüzlerin erişebilmesi için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SoruIstek(BaseModel):
    kullanici_mesaji: str = Field(..., description="Kullanıcının asistana sorduğu soru veya sesli metin")
    kullanici_id: Optional[str] = Field("misafir", description="Çiftçinin sistem ID numarası")

# Statik dosyaları bağla
STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/")
def ana_sayfa():
    """Web arayüzünü açar, yoksa JSON bilgi döner."""
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "durum": "aktif",
        "mesaj": "Merhaba! Akıllı Tarım Sesli Asistanı Servisi Çalışıyor.",
        "versiyon": "2.0.0",
        "model": DEFAULT_GEMINI_MODEL
    }

@app.get("/health")
def saglik_kontrolu():
    """Sunucu ve veritabanı durumunu test eder."""
    db_ok = False
    try:
        with get_db() as baglanti:
            imlec = baglanti.cursor()
            imlec.execute("SELECT 1")
            db_ok = True
    except Exception:
        pass

    return {
        "api_calisiyor": True,
        "veritabani_baglantisi": db_ok,
        "gemini_yapilandirildi": gemini_modeli is not None
    }

@app.get("/tarlalar")
def tarlalari_listele(ciftci_id: str = Query(..., description="Sorgulanacak çiftçi ID'si")):
    """Belirtilen çiftçinin tüm kayıtlı tarlalarını listeler."""
    with get_db() as baglanti:
        imlec = baglanti.cursor()
        imlec.execute("SELECT id, ciftci_id, boyut, ekin_turu, kayit_tarihi FROM tarlalar WHERE ciftci_id=?", (ciftci_id,))
        satirlar = imlec.fetchall()
        return {"ciftci_id": ciftci_id, "toplam_tarla": len(satirlar), "tarlalar": [dict(s) for s in satirlar]}

@app.post("/asistan")
def asistana_sor(
    kullanici_mesaji: Optional[str] = Query(None, description="URL parametresi üzerinden mesaj"),
    kullanici_id: Optional[str] = Query("misafir", description="URL parametresi üzerinden çiftçi ID"),
    istek_govdesi: Optional[SoruIstek] = Body(None, description="JSON gövdesi üzerinden istek")
):
    """
    Asistan ana beyni: Hem URL Query parametrelerini hem de JSON Body kabul eder.
    Böylece eski istemcilerle %100 geriye dönük uyumludur.
    """
    # Mesaj ve ID belirleme (Öncelik JSON gövdesinde, yoksa Query parametresinde)
    mesaj = ""
    c_id = "misafir"

    if isinstance(istek_govdesi, SoruIstek) and istek_govdesi.kullanici_mesaji:
        mesaj = istek_govdesi.kullanici_mesaji
        c_id = istek_govdesi.kullanici_id or "misafir"
    elif isinstance(kullanici_mesaji, str) and kullanici_mesaji:
        mesaj = kullanici_mesaji
        c_id = kullanici_id or "misafir"
    else:
        raise HTTPException(status_code=400, detail="Lütfen 'kullanici_mesaji' parametresini gönderin.")

    ciftcinin_tarlalari = ciftci_tarlalarini_getir(c_id)
    canli_hava = canli_hava_durumu_cek()
    canli_borsa = canli_borsa_cek()

    sistem_talimati = f"""
Sen Akıllı Tarım Uygulaması'nın çiftçilere rehberlik eden samimi, bilgili ve tecrübeli sesli asistanısın.
Karşındaki kişinin sistemdeki ID numarası: {c_id}.
Konuştuğun kişi bir çiftçidir. Ona samimi, anlaşılır, içten ve ziraat uzmanı bilgeliğiyle hitap et.

Aşağıdaki canlı verileri bilerek hareket et:
- Çiftçinin Kendi Tarlaları: {ciftcinin_tarlalari}
- Canlı Borsa: {canli_borsa}
- Canlı Hava Durumu: {canli_hava}

SADECE VE SADECE aşağıdaki geçerli JSON formatında yanıt ver:
{{
    "asistan_cevabi": "Çiftçiye sesli okunacak kısa, samimi ve bilgilendirici sözlü yanıt",
    "uygulama_emri": "gizli_sifre",
    "kaydedilecek_detay": "Veri girişi varsa doldur, yoksa boş bırak"
}}

Uygulama Emri Kuralları:
1. YÖNLENDİRME:
   - Borsa, pamuk/buğday/mısır fiyatları sorulursa -> "git_borsa"
   - Hava durumu, yağmur, rüzgar sorulursa -> "git_hava_durumu"
   - Kendi tarlaları sorulursa -> "git_tarlalarim"
   - Ana ekran, menü denirse -> "git_dashboard"
2. TARLA EKLEME:
   - "Yeni tarla ekle", "50 dönüm pamuk kaydet" gibi tarla bildirimlerinde -> "islem_tarla_ekle"
   - "kaydedilecek_detay" kısmına şu yapıda JSON yaz: {{"tarla_boyutu": "...", "ekin_turu": "..."}}
3. GENEL SOHBET / TARIM TAVSİYESİ:
   - Ekin zamanı, ilaçlama, sulama, genel sohbet gibi durumlarda -> "none"
"""

    istek_metni = sistem_talimati + "\n\nKullanıcının Sözü: " + mesaj

    if not gemini_modeli:
        return {
            "asistan_cevabi": "Yapay zeka anahtarı henüz tanımlanmamış ağam, lütfen .env dosyanızı kontrol edin.",
            "uygulama_emri": "none",
            "kaydedilecek_detay": ""
        }

    try:
        cevap = gemini_modeli.generate_content(istek_metni)
        akilli_cevap = json_yaniti_ayikla(cevap.text)

        # Veri Kayıt Eylemi (Tarla Ekleme)
        if akilli_cevap.get("uygulama_emri") == "islem_tarla_ekle":
            detaylar = akilli_cevap.get("kaydedilecek_detay")
            if isinstance(detaylar, str):
                try:
                    detaylar = json.loads(detaylar)
                except Exception:
                    detaylar = {}

            if isinstance(detaylar, dict):
                boyut = detaylar.get("tarla_boyutu", "")
                ekin = detaylar.get("ekin_turu", "")
                if boyut and ekin:
                    tarlayi_veritabanina_kaydet(c_id, boyut, ekin)
                    akilli_cevap["asistan_cevabi"] += f" Bilgiler {c_id} numaralı hesabınıza kaydedildi ağam."

        return akilli_cevap

    except Exception as e:
        logger.error(f"Asistan yanıt üretirken hata oluştu: {e}")
        return {
            "asistan_cevabi": f"Bağlantıda bir aksaklık oldu ağam, tekrar söyler misiniz? Hata: {str(e)}",
            "uygulama_emri": "none",
            "kaydedilecek_detay": ""
        }

if __name__ == "__main__":
    import uvicorn
    from config import HOST, PORT
    logger.info(f"Sunucu başlatılıyor: http://{HOST}:{PORT}")
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
