import cv2
import easyocr
import time
import numpy as np

print("EasyOCR modelleri yükleniyor, lütfen bekleyin...")
reader = easyocr.Reader(['tr', 'en']) 
print("Modeller yüklendi! Kamera açılıyor...")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

cv2.namedWindow('Tarama Ekrani', cv2.WINDOW_NORMAL)
cv2.resizeWindow('Tarama Ekrani', 960, 540)

aligned_start_time = None
REQUIRED_TIME = 2.0  # 2 saniye sabit bekleme süresi

while True:
    ret, frame = cap.read()
    if not ret:
        break

    height, width = frame.shape[:2]
    
    # Kutu boyutları
    box_w, box_h = 600, 380
    box_x = (width - box_w) // 2
    box_y = (height - box_h) // 2
    box_color = (255, 0, 0)
    
    # 1. Görüntüyü hazırla (Daha yumuşak bir bulanıklaştırma)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (7, 7), 0)
    
    # 2. Canny Eşiklerini Düşür (Daha az zıtlıkta bile çizgiyi bulsun)
    edges = cv2.Canny(blurred, 30, 150)

    # 3. YENİ EKLENTİ: Kopuk çizgileri "Genişlet" (Dilate) ve birleştir
    kernel = np.ones((5, 5), np.uint8)
    dilated_edges = cv2.dilate(edges, kernel, iterations=2)

    # Konturları artık kalınlaştırılmış çizgiler üzerinden ara
    contours, _ = cv2.findContours(dilated_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    is_currently_aligned = False
    best_x, best_y, best_w, best_h = 0, 0, 0, 0

    for contour in contours:
        area = cv2.contourArea(contour)
        
        # Alan limitini çok düşürdük (Kartı uzaktan tutarsan diye)
        if area > 15000: 
            x, y, w, h = cv2.boundingRect(contour)

            # YENİ TOLERANS: Kutunun sınırlarını çok daha esnek hale getirdik
            # (Kart kutudan 100 piksel taşabilir veya daha küçük olabilir)
            if (x >= box_x - 100 and y >= box_y - 100 and 
                x + w <= box_x + box_w + 100 and y + h <= box_y + box_h + 100):
                
                is_currently_aligned = True
                best_x, best_y, best_w, best_h = x, y, w, h
                break # Doğru objeyi bulduk, diğerlerine bakmaya gerek yok

    if is_currently_aligned:
        if aligned_start_time is None:
            aligned_start_time = time.time()
        
        elapsed_time = time.time() - aligned_start_time
        kalan_sure = max(0, REQUIRED_TIME - elapsed_time)
        box_color = (0, 255, 0) 
        
        cv2.putText(frame, f"Sabit Tutun... {kalan_sure:.1f} sn", (box_x, box_y - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # 2 saniye dolduysa FOTOĞRAF ÇEK VE FİLTRESİZ OKU
        if elapsed_time >= REQUIRED_TIME:
            cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), (0, 255, 255), 4)
            cv2.putText(frame, "FOTOGRAF CEKILDI - ISLENIYOR...", (box_x, box_y - 20), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 3)
            cv2.imshow('Tarama Ekrani', frame)
            cv2.waitKey(1)

            # O anki kareyi kes (Renkli olarak alıyoruz)
            roi = frame[best_y:best_y+best_h, best_x:best_x+best_w]
            
            # detail=0 ile metinleri bir liste olarak alıyoruz
            results = reader.readtext(roi, detail=0)
            
            print("\n" + "="*50)
            print("📸 FOTOĞRAF ÇEKİLDİ! İŞTE YAPAY ZEKANIN GÖRDÜĞÜ HAM METİNLER:")
            print("-" * 50)
            
            if len(results) == 0:
                print("Hata: Kutu içinde hiçbir yazı tespit edilemedi!")
                print("Lütfen ışığı artırın veya kartı kameraya yaklaştırın.")
            else:
                # Bulduğu her kelimeyi/cümleyi satır satır yazdır
                for i, metin in enumerate(results, 1):
                    print(f"[{i}] -> {metin}")
                    
            print("="*50 + "\n")
            
            aligned_start_time = None
            cv2.putText(frame, "OKUMA BASARILI! YENI KART BEKLENIYOR...", (50, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 3)
            cv2.imshow('Tarama Ekrani', frame)
            cv2.waitKey(3000)

    else:
        aligned_start_time = None
        cv2.putText(frame, "Karti mavi kutuya yerlestirin", (box_x, box_y - 20), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2)

    cv2.rectangle(frame, (box_x, box_y), (box_x + box_w, box_y + box_h), box_color, 3)
    cv2.imshow('Tarama Ekrani', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()