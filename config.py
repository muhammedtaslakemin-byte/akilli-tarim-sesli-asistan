"""
Yapılandırma Modülü (Configuration)
===================================
Tüm ortam değişkenleri, dosya yolları ve sistem ayarları tek bir merkezden yönetilir.
Windows konsol UTF-8 kodlama uyumluluğu sağlanır.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Windows konsolunda Türkçe karakter ve emoji kaynaklı UnicodeEncodeError hatalarını önler
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Proje Kök Dizini
BASE_DIR = Path(__file__).resolve().parent

# .env dosyasını yükle
load_dotenv(BASE_DIR / ".env")

# Google Gemini API Yapılandırması
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Veritabanı Yolu (Göreli yolların çalışma dizinine göre kaybolmasını engeller)
DB_PATH = BASE_DIR / "ciftci_verileri.db"

# Sunucu Yapılandırması
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
API_URL = f"http://{HOST}:{PORT}/asistan"

# Varsayılan Çiftçi Kimliği
DEFAULT_FARMER_ID = os.getenv("DEFAULT_FARMER_ID", "205")

# Hava Durumu Servis Koordinatları (Varsayılan: Şanlıurfa)
WEATHER_CITY = os.getenv("WEATHER_CITY", "Şanlıurfa")
WEATHER_LATITUDE = float(os.getenv("WEATHER_LATITUDE", "37.16"))
WEATHER_LONGITUDE = float(os.getenv("WEATHER_LONGITUDE", "38.79"))
