import cv2
import json
import base64
import numpy as np
import easyocr
import requests
import re
from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from datetime import datetime

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

print("="*50)
print("KİMLİK TANIMA SİSTEMİ BAŞLATILIYOR (RESMİ KURALLAR)...")
print("="*50)

print("EasyOCR modeli yükleniyor...")
reader = easyocr.Reader(['tr', 'en'], gpu=True)  
print("Sistem Hazır!")

# def extract_identity_info(full_text):
#     system_prompt = f"""
#     Sen kimlik kartı verilerini ayıklayan kesin bir veri çıkarma robotusun.
#     Aşağıdaki OCR metnini analiz et ve SADECE JSON formatında yanıt ver.

#     KİMLİK KARTI YAPISI VE KURALLAR:
#     1. soyad: Kimliklerde önce "Soyadı / Surname" (veya "Sumame", "Suname") yazar, gerçek soyisim BU ETİKETTEN SONRA gelir. Etiketi sil, sadece SOYADINI (örn: İZMİRLİ) al.
#     2. ad: Kimliklerde "Adı / Given Name(s)" yazar. Gerçek isim BU ETİKETTEN SONRA gelir. İsimler arasında noktalama işareti olmadan sadece boşluk olacak şekilde kalmalı. İSİM BİRDEN FAZLA KELİME OLABİLİR (Örn: "Hüseyin Serhat", "Mehmet Ali"). Etiketleri sil, tüm isimleri al.
#     3. tc_kimlik: Sadece 11 haneli rakam dizisidir.
#     4. dogum_tarihi: Sadece GG.AA.YYYY formatı. Doğum tarihi son geçerlilik tarihinden eski olmalıdır.
#     5. cinsiyet: Sadece "ERKEK" veya "KADIN" yaz. (Metinde E/M = ERKEK, K/F = KADIN).
#     6. son_gecerlilik: GG.AA.YYYY formatındaki ikinci tarihtir.
#     7. seri_no: Tam 9 karakterdir, harfler ve rakamlar içerir sıralaması harf + rakam + rakam + harf + rakam + rakam + rakam + rakam + rakam (Örn: A12B34567).

#     OCR Metni:
#     {full_text}
#     """

#     url = "http://localhost:11434/api/generate"
#     payload = {
#         "model": "llama3.2:3b",  
#         "prompt": system_prompt,
#         "format": "json",
#         "stream": False,
#         "options": {"temperature": 0.0}
#     }

#     try:
#         response = requests.post(url, json=payload, timeout=60)
#         response_data = response.json()
#         if 'error' in response_data: return None
#         return json.loads(response_data['response'])
#     except Exception as e:
#         print(f"LLM Hatası: {e}")
#         return None

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('process_frame')
def handle_frame(data):
    try:
        image_data = data.get('image')
        if not image_data:
            emit('result', {'error': 'Görüntü eksik'})
            return

        image_bytes = base64.b64decode(image_data.split(',')[1])
        np_array = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            emit('result', {'error': 'Geçersiz görüntü'})
            return
        
        roi = frame

        # EasyOCR İşlemi
        results = reader.readtext(roi, detail=0)
        full_ocr_text = " ".join(results)
        
        if not full_ocr_text.strip():
            emit('result', {'error': 'Kimlik tespit edilemedi, lütfen daha net gösterin.'})
            return

        # LLM Çözümlemesi
        # kimlik_bilgileri = extract_identity_info(full_ocr_text)
        
        _, buffer = cv2.imencode('.jpg', roi)
        roi_b64 = base64.b64encode(buffer).decode('utf-8')
        
        timestamp = datetime.now().strftime('%H:%M:%S')

        # raw_texts verisini arayüze iletiyoruz
        emit('result', {
            'success': True,
            'raw_texts': results, # OCR'ın gördüğü ham metin dizisi
            'kimlik_bilgileri': full_ocr_text,
            'timestamp': timestamp,
            'cropped_image': roi_b64
        })
        
    except Exception as e:
        print(f"Sunucu Hatası: {e}")
        emit('result', {'error': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)