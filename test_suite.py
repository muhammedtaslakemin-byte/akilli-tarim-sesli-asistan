"""
Otomatik Test Paketi (Unit & Integration Tests)
==============================================
Tüm bileşenleri test eder:
1. SQLite Veritabanı ve Tarla Kaydı
2. JSON Ayrıştırma ve Hata Dayanıklılığı
3. Canlı Hava Durumu API'si
4. FastAPI Uç Noktaları ve Sağlık Kontrolü
"""

import sys
import os
import unittest
from pathlib import Path

# Proje dizinini sys.path'e ekle
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Windows UTF-8 desteği
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import main
from config import BASE_DIR, WEATHER_CITY

class TestTarimAsistani(unittest.TestCase):

    def setUp(self):
        main.veritabani_kurulumu()

    def test_01_veritabani_ekleme_ve_okuma(self):
        """Veritabanına tarla ekleme ve çiftçi tarlalarını getirme testi."""
        test_ciftci = "test_999"
        # Tarla ekle
        tarla_id = main.tarlayi_veritabanina_kaydet(test_ciftci, "75 dönüm", "Pamuk")
        self.assertIsNotNone(tarla_id)
        self.assertGreater(tarla_id, 0)

        # Doğal dil metnini kontrol et
        metin = main.ciftci_tarlalarini_getir(test_ciftci)
        self.assertIn("75 dönüm", metin)
        self.assertIn("Pamuk", metin)

        # Temizlik
        with main.get_db() as conn:
            conn.cursor().execute("DELETE FROM tarlalar WHERE ciftci_id=?", (test_ciftci,))
            conn.commit()

    def test_02_json_ayiklama_saglamligi(self):
        """Gemini'den gelebilecek farklı markdown ve JSON formatlarını test eder."""
        # 1. Düz JSON
        d1 = '{"asistan_cevabi": "Merhaba", "uygulama_emri": "none", "kaydedilecek_detay": ""}'
        r1 = main.json_yaniti_ayikla(d1)
        self.assertEqual(r1["uygulama_emri"], "none")

        # 2. Markdown Kod Bloğu içinde JSON
        d2 = '```json\n{"asistan_cevabi": "Pamuk fiyatı güncellendi", "uygulama_emri": "git_borsa", "kaydedilecek_detay": ""}\n```'
        r2 = main.json_yaniti_ayikla(d2)
        self.assertEqual(r2["uygulama_emri"], "git_borsa")

        # 3. Öncesinde ve sonrasında metin olan JSON
        d3 = 'Tabii ki efendim, işte cevabınız:\n{"asistan_cevabi": "Kaydettim", "uygulama_emri": "islem_tarla_ekle", "kaydedilecek_detay": {"tarla_boyutu": "20 dönüm", "ekin_turu": "Mısır"}}\nİyi günler.'
        r3 = main.json_yaniti_ayikla(d3)
        self.assertEqual(r3["uygulama_emri"], "islem_tarla_ekle")

    def test_03_canli_hava_durumu(self):
        """Hava durumu servisinin yanıt verdiğini veya hataya düşmeden güvenli döndüğünü test eder."""
        hava = main.canli_hava_durumu_cek()
        self.assertIsInstance(hava, str)
        self.assertTrue(len(hava) > 5)

    def test_04_canli_borsa(self):
        """Borsa fiyat bilgisinin döndüğünü test eder."""
        borsa = main.canli_borsa_cek()
        self.assertIn("Pamuk", borsa)
        self.assertIn("Buğday", borsa)

    def test_05_saglik_kontrolu_endpoint(self):
        """FastAPI /health uç noktasını test eder."""
        sonuc = main.saglik_kontrolu()
        self.assertTrue(sonuc["api_calisiyor"])
        self.assertTrue(sonuc["veritabani_baglantisi"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
