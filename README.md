# 🪪 ID_CARD_DETECTION - Akıllı Kimlik ve Belge Okuyucu (OCR)

Bu proje, bilgisayarınızın veya telefonunuzun kamerasını kullanarak **T.C. Kimlik Kartı**, **Uluslararası Pasaport** ve **Biniş Kartı (Boarding Pass)** gibi belgeleri otomatik olarak okuyup yapılandırılmış verilere (JSON) dönüştüren web tabanlı bir OCR (Optik Karakter Tanıma) sistemidir.

Proje, gücünü **EasyOCR** motorundan alır ve karmaşık metin yığınlarından sadece istenen bilgileri çekebilmek için gelişmiş Regex algoritmaları kullanır.

## ✨ Temel Özellikler

*   **Çoklu Belge Desteği:** T.C. Kimlik Kartı, Pasaport MRZ (Makine Okunabilir Alan) ve Biniş Kartı desteği.
*   **Tarayıcı Tabanlı Kırpma (Smart Crop):** Sistem, performansı artırmak için büyük kamera karesinin tamamını değil, yalnızca kullanıcının ekranda gördüğü "yeşil kılavuz kutu"nun içini matematiksel olarak kesip sunucuya gönderir. Bu, işlemi inanılmaz hızlandırır.
*   **Gerçek Zamanlı İletişim:** Flask-SocketIO sayesinde kamera akışı ve OCR sonuçları anlık olarak sayfa yenilenmeden ekrana yansır.
*   **Tamamen Çevrimdışı (Offline):** Sistem hiçbir veriyi dış bulut API'lerine (Google Vision vb.) göndermez; tamamen kendi donanımınızda çalışarak KVKK/GDPR ihlallerinin önüne geçer.

## 📥 Girdi ve Çıktı (Input / Output) Örneği

Sistem, kameradan yakalanan hedef alanı bir **Base64 Görüntü** (Girdi) olarak alır ve arka planda işleyerek web arayüzüne aşağıdaki gibi yapılandırılmış bir **JSON objesi** (Çıktı) döndürür:

**Örnek API Yanıtı (T.C. Kimlik Kartı için):**

{
  "success": true,
  "doc_type": "id_card",
  "extracted_data": {
    "tc_kimlik": "12345678901",
    "ad": "AHMET",
    "soyad": "YILMAZ",
    "dogum_tarihi": "01.01.1990",
    "cinsiyet": "ERKEK",
    "seri_no": "A11B12345",
    "son_gecerlilik": "01.01.2030",
    "anne_adi": "",
    "baba_adi": ""
  },
  "cropped_image": "base64_kodlanmis_gorsel_verisi..."
}

## 📁 Proje Yapısı

GitHub deposunda yer alan dosyaların temel görevleri şöyledir:

*   **app.py:** Web sunucusunu (Flask) başlatan, EasyOCR motorunu çalıştıran ve Regex ayıklama mantığını barındıran ana arka uç (Backend) dosyasıdır. Sistemi ayağa kaldırmak için bu dosyayı çalıştırmanız yeterlidir.
*   **templates/:** Web arayüzünün bulunduğu klasördür. İçerisindeki index.html dosyası; kamerayı açar, görüntüleri kırpar ve arayüzü oluşturur.
*   **kimlik bilgileri.py & kimlik_dogrulama.py:** Çeşitli ekstra özellikler ve geliştirme aşamasındaki test kodlarını barındırır.

## 🛠️ Kurulum ve Çalıştırma

Projeyi kendi bilgisayarınızda çalıştırmak için aşağıdaki adımları izleyebilirsiniz. Sistemin hızlı çalışması için bilgisayarınızda bir NVIDIA GPU (CUDA) bulunması tavsiye edilir, ancak CPU ile de sorunsuz çalışır.

1. Depoyu Klonlayın

git clone https://github.com/hserhatizmirli/ID_CARD_DETECTION.git
cd ID_CARD_DETECTION


2. Gerekli Kütüphaneleri Yükleyin

Python sürümünüzün (tercihen 3.9+) kurulu olduğundan emin olduktan sonra bağımlılıkları yükleyin:

pip install flask flask-socketio flask-cors easyocr opencv-python numpy


3. Uygulamayı Başlatın

python app.py


4. Arayüze Erişin

Terminalde uygulamanın başladığını gördükten sonra tarayıcınızdan http://localhost:5000 veya http://127.0.0.1:5000 adresine gidin. Tarayıcı kamera izni istediğinde onay vererek sistemi kullanmaya başlayabilirsiniz.
