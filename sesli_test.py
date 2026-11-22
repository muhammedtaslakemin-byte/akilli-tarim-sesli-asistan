"""
Sesli Asistan İstemcisi ve Test Modülü (Mikrofon & Hoparlör)
============================================================
Kullanıcının mikrofondan sesini dinler (Google Speech-to-Text),
FastAPI backend servisine iletir ve gelen yanıtı sesli olarak okur (gTTS + pygame).
Mikrofon bulunamadığında otomatik olarak klavye girişine geçer.
"""

import sys
import os
import time
import glob
import uuid
import requests
import speech_recognition as sr
from gtts import gTTS

# Windows konsol UTF-8 desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Pygame ses motorunu başlat
try:
    import pygame
    pygame.mixer.init()
    SES_MOTORU_HAZIR = True
except Exception as e:
    print(f"[UYARI] Pygame başlatılamadı: {e}")
    SES_MOTORU_HAZIR = False

# Yapılandırma
try:
    from config import API_URL, DEFAULT_FARMER_ID
except ImportError:
    API_URL = "http://127.0.0.1:8000/asistan"
    DEFAULT_FARMER_ID = "205"

KULLANICI_ID = DEFAULT_FARMER_ID

def eski_sesleri_temizle():
    """Önceki oturumlardan kalan geçici mp3 dosyalarını siler."""
    for dosya in glob.glob("cevap_*.mp3"):
        try:
            os.remove(dosya)
        except Exception:
            pass

def sesli_oku(metin: str):
    """Metni seslendirir ve hoparlörden çalar."""
    print(f"\n🤖 Asistan: {metin}\n")
    eski_sesleri_temizle()

    if not SES_MOTORU_HAZIR:
        return

    dosya_adi = f"cevap_{uuid.uuid4().hex}.mp3"
    try:
        # Google Text-to-Speech ile Türkçe ses dosyası üret
        tts = gTTS(text=metin, lang="tr")
        tts.save(dosya_adi)

        # Pygame ile oynat
        pygame.mixer.music.load(dosya_adi)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        pygame.mixer.music.unload()

        # Oynatma bitince dosyayı temizle
        try:
            if os.path.exists(dosya_adi):
                os.remove(dosya_adi)
        except Exception:
            pass

    except Exception as e:
        # İnternet yoksa veya gTTS başarısızsa yerel pyttsx3 deneyelim
        try:
            import pyttsx3
            motor = pyttsx3.init()
            motor.say(metin)
            motor.runAndWait()
        except Exception:
            print(f"[HATA] Seslendirme yapılamadı: {e}")

def asistan_ile_sohbet_et():
    """Ana sesli sohbet döngüsü."""
    dinleyici = sr.Recognizer()
    sesli_oku("Sistem hazır ağam, seni dinliyorum.")

    mikrofon_var = True
    try:
        with sr.Microphone() as test_kaynak:
            pass
    except Exception as e:
        print(f"[UYARI] Mikrofon algılanamadı ({e}). Klavye moduna geçiliyor.")
        mikrofon_var = False

    while True:
        ciftci_metni = ""
        if mikrofon_var:
            print("\n🎤 Konuşabilirsin... (Kapatmak için 'Kapat' de veya 'K' yazıp Enter'a bas)")
            try:
                with sr.Microphone() as kaynak:
                    dinleyici.adjust_for_ambient_noise(kaynak, duration=0.8)
                    ses = dinleyici.listen(kaynak, timeout=5, phrase_time_limit=10)
                    ciftci_metni = dinleyici.recognize_google(ses, language="tr-TR")
                    print(f"🗣️ Sen dedin ki: {ciftci_metni}")
            except sr.WaitTimeoutError:
                continue
            except sr.UnknownValueError:
                print("Sesi tam anlayamadım ağam.")
                continue
            except Exception as e:
                print(f"[UYARI] Mikrofon hatası: {e}. Klavyeye geçiliyor.")
                mikrofon_var = False
                continue
        else:
            try:
                ciftci_metni = input("\n⌨️ Mesajınızı yazın (Çıkış için 'kapat'): ").strip()
            except (KeyboardInterrupt, EOFError):
                break

        if not ciftci_metni:
            continue

        if "kapat" in ciftci_metni.lower():
            sesli_oku("Görüşmek üzere ağam, bereketli günler!")
            break

        # Mesajı FastAPI servisine gönder
        try:
            cevap = requests.post(
                API_URL,
                json={"kullanici_mesaji": ciftci_metni, "kullanici_id": KULLANICI_ID},
                timeout=15
            )

            if cevap.status_code == 200:
                robot_verisi = cevap.json()
                print(f"   [GİZLİ ŞİFRE]: {robot_verisi.get('uygulama_emri')}")
                print(f"   [KAYIT DETAYI]: {robot_verisi.get('kaydedilecek_detay')}")
                sesli_oku(robot_verisi.get("asistan_cevabi", ""))
            else:
                sesli_oku(f"Sunucudan yanıt alınamadı. Durum kodu: {cevap.status_code}")
        except requests.exceptions.ConnectionError:
            sesli_oku("Bağlantı hatası! Lütfen önce 'python main.py' servisini başlatın.")
            time.sleep(1)
        except Exception as e:
            print(f"[HATA]: {e}")

if __name__ == "__main__":
    try:
        asistan_ile_sohbet_et()
    except KeyboardInterrupt:
        print("\nAsistan kapatıldı.")
        eski_sesleri_temizle()
