"""
Akıllı Tarım Sesli ve Yazılı Asistan İstemcisi
=============================================
Kullanıcı dostu, ses ve klavye destekli modern konsol arayüzü.
"""

import sys
import os
import time
import uuid
import glob
import requests

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from config import API_URL, DEFAULT_FARMER_ID
except ImportError:
    API_URL = "http://127.0.0.1:8000/asistan"
    DEFAULT_FARMER_ID = "205"

def ses_cal(metin: str):
    """Metni sesli olarak okur."""
    print(f"\n🌾 ASİSTAN: {metin}\n")
    try:
        from gtts import gTTS
        import pygame
        pygame.mixer.init()

        dosya = f"temp_{uuid.uuid4().hex}.mp3"
        tts = gTTS(text=metin, lang="tr")
        tts.save(dosya)

        pygame.mixer.music.load(dosya)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()

        if os.path.exists(dosya):
            os.remove(dosya)
    except Exception:
        # Fallback offline TTS
        try:
            import pyttsx3
            motor = pyttsx3.init()
            motor.say(metin)
            motor.runAndWait()
        except Exception:
            pass

def istek_gonder(mesaj: str, ciftci_id: str = DEFAULT_FARMER_ID):
    """API servisine istek gönderir ve sonucu ekrana yansıtır."""
    try:
        yanit = requests.post(
            API_URL,
            json={"kullanici_mesaji": mesaj, "kullanici_id": ciftci_id},
            timeout=15
        )
        if yanit.status_code == 200:
            veri = yanit.json()
            komut = veri.get("uygulama_emri", "none")
            kayit = veri.get("kaydedilecek_detay", "")
            cevap = veri.get("asistan_cevabi", "")

            print(f"👉 Sistem Emri : {komut}")
            if kayit:
                print(f"📋 Kayıt Bilgi : {kayit}")

            ses_cal(cevap)
            return veri
        else:
            print(f"[HATA] Sunucu Yanıtı: {yanit.status_code}")
    except requests.exceptions.ConnectionError:
        print("[HATA] main.py API sunucusuna bağlanılamadı! Lütfen sunucunun açık olduğundan emin olun.")
    except Exception as e:
        print(f"[HATA] Beklenmeyen hata: {e}")
    return None

def klavye_modu(ciftci_id: str):
    """Klavye üzerinden hızlı soru-cevap modu."""
    print("\n--- KLAVYE MODU BAŞLATILDI (Çıkış için 'q' veya 'kapat') ---")
    while True:
        try:
            girdi = input("Soru Sor > ").strip()
            if not girdi:
                continue
            if girdi.lower() in ["q", "kapat", "exit", "quit"]:
                print("Klavye modundan çıkılıyor...")
                break
            istek_gonder(girdi, ciftci_id)
        except (KeyboardInterrupt, EOFError):
            break

def mikrofon_modu(ciftci_id: str):
    """Mikrofon dinleme modu."""
    try:
        import speech_recognition as sr
    except ImportError:
        print("[HATA] speech_recognition kütüphanesi kurulu değil.")
        return

    dinleyici = sr.Recognizer()
    try:
        mic = sr.Microphone()
    except Exception as e:
        print(f"[UYARI] Mikrofon algılanamadı ({e}). Klavye moduna yönlendiriliyorsunuz.")
        klavye_modu(ciftci_id)
        return

    ses_cal("Sistem hazır ağam, dinliyorum.")
    while True:
        try:
            with mic as kaynak:
                print("\n🎙️ Dinleniyor... (Kapatmak için 'kapat' deyin)")
                dinleyici.adjust_for_ambient_noise(kaynak, duration=0.6)
                ses = dinleyici.listen(kaynak, timeout=5, phrase_time_limit=10)
                metin = dinleyici.recognize_google(ses, language="tr-TR")
                print(f"🗣️ Algılanan: {metin}")

                if "kapat" in metin.lower():
                    ses_cal("Görüşmek üzere ağam.")
                    break

                istek_gonder(metin, ciftci_id)
        except sr.WaitTimeoutError:
            continue
        except sr.UnknownValueError:
            print("Ne dediğinizi tam anlayamadım.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[UYARI]: {e}")
            break

def ana_menu():
    ciftci_id = DEFAULT_FARMER_ID
    banner = r"""
  ╔═══════════════════════════════════════════════════════════════╗
  ║          AKILLI TARIM SESLİ ASİSTANINA HOŞ GELDİNİZ          ║
  ║          Google Gemini & FastAPI Destekli Çiftçi Dostu       ║
  ╚═══════════════════════════════════════════════════════════════╝
    """
    print(banner)
    print(f"Aktif Çiftçi ID: {ciftci_id}")
    print("1) Mikrofon ile Konuş (Sesli Mod)")
    print("2) Klavyeden Yaz (Hızlı Test Modu)")
    print("3) Çıkış")

    secim = input("\nSeçiminiz (1/2/3) [Varsayılan: 2]: ").strip()
    if secim == "1":
        mikrofon_modu(ciftci_id)
    elif secim == "3":
        print("İyi günler!")
    else:
        klavye_modu(ciftci_id)

if __name__ == "__main__":
    ana_menu()
