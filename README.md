# Akıllı Tarım Sesli Asistanı

Google Gemini ve FastAPI tabanlı, çiftçiler için sesli ve yazılı tarım danışmanlığı sunan yapay zeka asistanı.

## Özellikler

- **Sesli Etkileşim:** Mikrofondan konuşma algılama (SpeechRecognition) ve Türkçe sesli yanıt (gTTS / pygame).
- **Gemini Yapay Zeka:** Çiftçinin sorularına ziraat danışmanlığı ile yanıt verme ve yapılandırılmış JSON çıktısı üretme.
- **Canlı Veriler:** Open-Meteo ile anlık hava durumu ve tarımsal borsa fiyatları entegrasyonu.
- **Tarla Kayıt Sistemi:** Sesli olarak söylenen tarla bilgilerini SQLite veritabanında saklama.
- **Arayüz Entegrasyonu:** Web ve mobil arayüzler için yönlendirme komutları (`git_borsa`, `git_hava_durumu`, `git_tarlalarim`, vb.).

## Kurulum

1. Depoyu klonlayın ve klasöre girin:
   ```bash
   git clone https://github.com/muhammedtaslakemin-byte/akilli-tarim-sesli-asistan.git
   cd akilli-tarim-sesli-asistan
   ```

2. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt
   ```

3. `.env.example` dosyasını `.env` olarak kopyalayıp Gemini API anahtarınızı tanımlayın:
   ```bash
   cp .env.example .env
   ```

## Kullanım

### 1. API Servisini Başlatma
```bash
python main.py
```
Sunucu `http://127.0.0.1:8000` adresinde çalışmaya başlar. Dokümantasyona `http://127.0.0.1:8000/docs` üzerinden erişebilirsiniz.

### 2. Asistanı Çalıştırma
Sesli veya yazılı iletişim için:
```bash
python sesli_asistan.py
```
veya
```bash
python sesli_test.py
```

## Testler
Tüm bileşenleri test etmek için:
```bash
python test_suite.py
```
