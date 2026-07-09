import cv2
import base64
import numpy as np
import easyocr
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

print("="*50)
print("KİMLİK TANIMA SİSTEMİ BAŞLATILIYOR...")
print("="*50)

print("OCR modeli yükleniyor (Lütfen bekleyin)...")
reader = easyocr.Reader(['tr', 'en'])
print("OCR Hazır! Sunucu başlatılıyor...")

history = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/detect', methods=['POST'])
def detect_id():
    global history
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({'error': 'Görüntü verisi eksik'}), 400
            
        image_data = data['image'].split(',')[1]
        image_bytes = base64.b64decode(image_data)
        np_array = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            return jsonify({'error': 'Geçersiz görüntü'}), 400

        # === 85.6 mm / 54.0 mm Standart Kart Oranına Göre Kesim ===
        h, w = frame.shape[:2]
        card_ratio = 85.6 / 54.0 
        
        box_w = int(w * 0.8)
        box_h = int(box_w / card_ratio)
        
        if box_h > h * 0.8:
            box_h = int(h * 0.8)
            box_w = int(box_h * card_ratio)
            
        box_x = (w - box_w) // 2
        box_y = (h - box_h) // 2
        
        # Sadece yeşil kutunun içini kes
        roi = frame[box_y:box_y+box_h, box_x:box_x+box_w]

        # EasyOCR ile sadece kesilen bölgeyi oku
        results = reader.readtext(roi, detail=0)
        
        # Kullanıcıya neyi okuduğumuzu göstermek için kesilen bölgeyi Base64'e çevir
        _, buffer = cv2.imencode('.jpg', roi)
        roi_b64 = base64.b64encode(buffer).decode('utf-8')
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        full_text = " ".join(results) if len(results) > 0 else "YAZI BULUNAMADI"
        
        print(f"[{timestamp}] Manuel Tarama Yapıldı. Bulunan: {full_text}")
        
        return jsonify({
            'success': True,
            'raw_texts': results,
            'full_text': full_text,
            'timestamp': timestamp,
            'cropped_image': roi_b64  # Kesilen fotoğrafı da gönderiyoruz
        })
        
    except Exception as e:
        print(f"Hata: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("="*50)
    print("SUNUCU HAZIR: Tarayıcıdan http://127.0.0.1:8000 adresine gidin.")
    print("="*50)
    app.run(host='127.0.0.1', port=8000, debug=False, threaded=True)