import os
os.environ['OMP_NUM_THREADS'] = '1'

import cv2
import base64
import numpy as np
import re
from datetime import datetime
from flask import Flask, render_template
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import easyocr

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

print("="*50)
print("KİMLİK & BİNİŞ KARTI TANIMA SİSTEMİ BAŞLATILDI...")
print("="*50)

reader = easyocr.Reader(['tr', 'en'], gpu=True)
print("Sistem Hazır!")

# ==========================================
# YARDIMCI FONKSİYONLAR (Kimlik İçin)
# ==========================================
def remove_vowels(text):
    vowels = "AEIİOÖUÜ"
    return "".join([c for c in str(text).upper() if c not in vowels and c.isalpha()])

def is_consonant_match(text1, text2):
    if not text1 or not text2:
        return False
    return remove_vowels(text1) == remove_vowels(text2)

def parse_id_back_side(lines):
    back_side_data = {"anne_adi": "", "baba_adi": "", "veren_makam": "T.C. İÇİŞLERİ BAKANLIĞI", "mrz_data": {}}
    mrz_lines = []
    
    for i, line in enumerate(lines):
        upper_line = line.upper()
        if re.search(r'\b(ANNE|MOTHER)\b', upper_line):
            clean_inline = re.sub(r'\b(ANNE|MOTHER|ADI|NAME|S)\b', '', upper_line).replace("'", "").strip()
            clean_inline = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_inline).strip()
            if len(clean_inline) >= 2 and clean_inline not in ["ANNE ADI", "MOTHERS NAME"]:
                back_side_data["anne_adi"] = clean_inline
            else:
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', lines[j].upper()).strip()
                    if len(next_line) >= 2 and not re.search(r'\b(BABA|FATHER|VEREN|MAKAM|ISSUED)\b', next_line):
                        if next_line not in ["ANNE ADI", "MOTHERS NAME", "MOTHERSNAME"]:
                            back_side_data["anne_adi"] = next_line
                            break
                            
        if re.search(r'\b(BABA|FATHER)\b', upper_line):
            clean_inline = re.sub(r'\b(BABA|FATHER|ADI|NAME|S)\b', '', upper_line).replace("'", "").strip()
            clean_inline = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_inline).strip()
            if len(clean_inline) >= 2 and clean_inline not in ["BABA ADI", "FATHERS NAME"]:
                back_side_data["baba_adi"] = clean_inline
            else:
                for j in range(i + 1, min(i + 4, len(lines))):
                    next_line = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', lines[j].upper()).strip()
                    if len(next_line) >= 2 and not re.search(r'\b(VEREN|MAKAM|ISSUED)\b', next_line):
                        if next_line not in ["BABA ADI", "FATHERS NAME", "FATHERSNAME"]:
                            back_side_data["baba_adi"] = next_line
                            break

        upper_line_no_space = upper_line.replace(" ", "")
        if '<' in upper_line_no_space:
            clean_mrz = re.sub(r'[^A-Z0-9<]', '', upper_line_no_space)
            mrz_lines.append(clean_mrz)

    raw_mrz = "".join(mrz_lines)
    if len(raw_mrz) >= 60:
        mrz_data = {}
        tc_match = re.search(r'I<TUR([A-Z0-9<]{9})[0-9]([0-9]{11})', raw_mrz)
        if tc_match:
            mrz_data["seri_no"] = tc_match.group(1).replace('<', '')
            mrz_data["tc_kimlik"] = tc_match.group(2)
            
        skt_match = re.search(r'([0-9]{6})[0-9](M|F|<)([0-9]{6})[0-9]TUR', raw_mrz)
        if skt_match:
            if skt_match.group(2) == 'M': mrz_data["cinsiyet"] = "ERKEK"
            elif skt_match.group(2) == 'F': mrz_data["cinsiyet"] = "KADIN"
            try:
                mrz_data["dogum_tarihi"] = datetime.strptime(skt_match.group(1), "%y%m%d").strftime("%d.%m.%Y")
                mrz_data["son_gecerlilik"] = datetime.strptime(skt_match.group(3), "%y%m%d").strftime("%d.%m.%Y")
            except ValueError: pass
                
        name_match = re.search(r'TUR[<0-9]+([A-Z]+)<<([A-Z<]+)', raw_mrz)
        if name_match:
            mrz_data["soyad"] = name_match.group(1).replace('<', ' ').strip()
            mrz_data["ad"] = name_match.group(2).replace('<', ' ').strip()
        back_side_data["mrz_data"] = mrz_data
        
    return back_side_data

# ==========================================
# BİNİŞ KARTI (BOARDING PASS) ÇÖZÜMLEME
# ==========================================
def parse_boarding_pass(lines, full_text):
    bp_data = {
        "yolcu_adi": "",
        "ucus_no": "",
        "guzergah": "",
        "tarih": "",
        "koltuk": "",
        "kapi": ""
    }
    
    # 1. GÜZERGAH TESPİTİ (Geliştirilmiş Hibrit Yöntem)
    kalkis = ""
    varis = ""
    
    for i, line in enumerate(lines):
        upper_line = line.upper()
        
        # FROM / NEREDEN tespiti
        if re.search(r'\b(FROM|NEREDEN)\b', upper_line) and not kalkis:
            # Önce aynı satırda yazıp yazmadığına bak (Örn: "FROM ISTANBUL")
            clean_inline = re.sub(r'\b(FROM|NEREDEN|/|:|-)\b', '', upper_line).strip()
            clean_inline = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_inline).strip()
            
            if len(clean_inline) >= 3:
                kalkis = clean_inline
            elif i + 1 < len(lines):
                # Aynı satırda yoksa bir alt satıra in (Örn: FROM \n NEW YORK)
                clean_next = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', lines[i+1].upper()).strip()
                # Alt satırın başka bir etiket (TO, FLIGHT vb.) olmadığından emin ol
                if len(clean_next) >= 3 and not re.search(r'\b(TO|NEREYE|FLIGHT|DATE|NAME)\b', clean_next):
                    kalkis = clean_next
                    
        # TO / NEREYE tespiti
        if re.search(r'\b(TO|NEREYE)\b', upper_line) and not varis:
            clean_inline = re.sub(r'\b(TO|NEREYE|/|:|-)\b', '', upper_line).strip()
            clean_inline = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_inline).strip()
            
            if len(clean_inline) >= 3:
                varis = clean_inline
            elif i + 1 < len(lines):
                clean_next = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', lines[i+1].upper()).strip()
                if len(clean_next) >= 3 and not re.search(r'\b(FLIGHT|DATE|NAME|CLASS)\b', clean_next):
                    varis = clean_next

    # Eğer FROM ve TO etiketleriyle şehirler bulunduysa birleştir
    if kalkis and varis:
        bp_data["guzergah"] = f"{kalkis} - {varis}"
    else:
        # BULUNAMADIYSA YEDEK PLAN (B Planı): 3 Harfli IATA kodlarını ara (Örn: IST . JFK)
        route_match = re.search(r'\b([A-Z]{3})\s*[\.\-]\s*([A-Z]{3})\b', full_text)
        if route_match:
            bp_data["guzergah"] = f"{route_match.group(1)} - {route_match.group(2)}"

    # 2. UÇUŞ NUMARASI (Örn: TK 0001, F 0256)
    flight_match = re.search(r'\b([A-Z]{2})\s*(\d{3,4})\b', full_text)
    if flight_match:
        bp_data["ucus_no"] = f"{flight_match.group(1)} {flight_match.group(2)}"
        
    # 3. KOLTUK NO (Örn: 06G, 10A)
    seat_match = re.search(r'\b(\d{1,2}[A-K])\b', full_text)
    if seat_match:
        bp_data["koltuk"] = seat_match.group(1)
    else:
        seat_alt = re.search(r'SEAT[/A-Z]*\s*([0-9A-Z]+)', full_text)
        if seat_alt: bp_data["koltuk"] = seat_alt.group(1)
            
    # 4. KAPI / GATE (Örn: B1, 02)
    gate_match = re.search(r'GATE[/A-Z]*\s*([0-9A-Z]+)', full_text)
    if gate_match: 
        bp_data["kapi"] = gate_match.group(1)
        
    # 5. TARİH (Örn: 08OCT, JUN 17)
    date_match = re.search(r'\b(\d{1,2}[A-Z]{3}|[A-Z]{3}\s\d{1,2})\b', full_text)
    if date_match and not re.search(r'(IST|JFK|LHR)', date_match.group(1)):
        bp_data["tarih"] = date_match.group(1)

    # 6. İSİM TESPİTİ (NAME/ISIM etiketinden yola çıkarak)
    for i, line in enumerate(lines):
        upper_line = line.upper()
        if re.search(r'\b(NAME|ISIM|YOLCU|PASSENGER)\b', upper_line):
            if i + 1 < len(lines):
                clean_name = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', lines[i+1].upper()).strip()
                if len(clean_name) >= 3 and not re.search(r'\b(FLIGHT|GATE|SEAT)\b', clean_name):
                    bp_data["yolcu_adi"] = clean_name
                    break
                    
    # Eğer isim etiketle bulunamadıysa serbest metin içinde uzun bir ad/soyad yapısı ara
    if not bp_data["yolcu_adi"]:
        for line in lines:
            clean = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', line.upper()).strip()
            words = clean.split()
            # Uçuş veya bilet terimleri içermeyen, en az 2 kelime ve 8 karakterli yapı büyük ihtimal isimdir
            if len(words) >= 2 and len(clean) > 8 and not re.search(r'\b(BOARDING|PASS|FLIGHT|CLASS)\b', clean):
                bp_data["yolcu_adi"] = clean
                break

    return bp_data

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('process_frame')
def handle_frame(data):
    try:
        import time
        start_time = time.time()
        
        image_data = data.get('image')
        doc_type = data.get('doc_type', 'id_card') # Frontend'den gelen belge tipi
        
        if not image_data:
            emit('result', {'error': 'Görüntü eksik'})
            return

        image_bytes = base64.b64decode(image_data.split(',')[1])
        np_array = np.frombuffer(image_bytes, np.uint8)
        frame = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        
        if frame is None:
            emit('result', {'error': 'Geçersiz görüntü'})
            return
        
        results = reader.readtext(frame)
        if not results:
            emit('result', {'error': 'Belge okunamadı'})
            return
            
        sorted_results = sorted(results, key=lambda x: min([p[1] for p in x[0]]))
        lines = [res[1] for res in sorted_results]
        full_text = " ".join(lines).upper()

        response_data = {}

        # ==========================================
        # KİMLİK KARTI (ID CARD) OKUMA AKIŞI
        # ==========================================
        if doc_type == 'id_card':
            kimlik_bilgileri = {
                "tc_kimlik": "", "ad": "", "soyad": "", "dogum_tarihi": "",
                "son_gecerlilik": "", "cinsiyet": "", "seri_no": "",
                "anne_adi": "", "baba_adi": "", "mrz_data": {}
            }
            
            tc_match = re.search(r'\b\d{11}\b', full_text)
            if tc_match: kimlik_bilgileri["tc_kimlik"] = tc_match.group(0)

            seri_match = re.search(r'\b[A-ZÇĞİÖŞÜ]\d{2}[A-ZÇĞİÖŞÜ]\d{5}\b', full_text)
            if seri_match: kimlik_bilgileri["seri_no"] = seri_match.group(0)

            if re.search(r'\b(E/M|EIM|ERKEK| E | M )\b', full_text): kimlik_bilgileri["cinsiyet"] = "ERKEK"
            elif re.search(r'\b(K/F|KIF|KADIN| K | F )\b', full_text): kimlik_bilgileri["cinsiyet"] = "KADIN"

            dates = re.findall(r'\b\d{2}\.\d{2}\.\d{4}\b', full_text)
            valid_dates = []
            for dt in dates:
                try: valid_dates.append(datetime.strptime(dt, "%d.%m.%Y"))
                except ValueError: pass
            
            if len(valid_dates) >= 2:
                valid_dates.sort()
                kimlik_bilgileri["dogum_tarihi"] = valid_dates[0].strftime("%d.%m.%Y")
                kimlik_bilgileri["son_gecerlilik"] = valid_dates[-1].strftime("%d.%m.%Y")
            elif len(valid_dates) == 1:
                kimlik_bilgileri["dogum_tarihi"] = valid_dates[0].strftime("%d.%m.%Y")

            ad = ""
            soyad = ""
            ignore_surname = r'\b(SOYADI|SOYAD|SOYAD1|50YADI|SURNAME|SUMAME|SURMAME|SUNAME|SUNANC|SURAMC|SOYAQ|SIRNSNS|SURNANE|SURNAM|SURAAME|SCRADI|SOVADI|SMNMNO)\b'
            ignore_name = r'\b(ADI|AD|AD1|A0I|GIVEN|NAME|NANE|NAMES|GION|GEN|TDE|GURN|ERD|ERDS|ACI|GROXARUS|6IVEN|G1VEN|NAM|NME|NZMAS|GNSN|NAMXS|8O|80)\b'
            
            for i, line in enumerate(lines):
                upper_line = line.upper()
                if re.search(r'\b(SOYADI|SOYAD|SOYAD1|50YADI|SCRADI|SOVADI|SOYAQ)\b', upper_line):
                    clean_inline = re.sub(ignore_surname, '', upper_line)
                    clean_inline = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_inline).strip()
                    if len(clean_inline) >= 2:
                        soyad = clean_inline
                    else:
                        for j in range(i + 1, min(i + 4, len(lines))):
                            next_line = lines[j].upper()
                            if re.search(ignore_surname, next_line):
                                clean_next = re.sub(ignore_surname, '', next_line)
                                clean_next = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_next).strip()
                                if len(clean_next) >= 2:
                                    soyad = clean_next
                                    break
                                continue
                            clean_next = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', next_line).strip()
                            if len(clean_next) >= 2:
                                soyad = clean_next
                                break

                if re.search(r'\b(ADI|AD|AD1|A0I|GNSN|6IVEN|G1VEN)\b', upper_line) and not re.search(r'\b(SOYADI|SOYAD|SCRADI|SOVADI)\b', upper_line):
                    clean_inline = re.sub(ignore_name, '', upper_line)
                    clean_inline = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_inline).strip()
                    if len(clean_inline) >= 2:
                        ad = clean_inline
                    else:
                        for j in range(i + 1, min(i + 4, len(lines))):
                            next_line = lines[j].upper()
                            if re.search(ignore_name, next_line):
                                clean_next = re.sub(ignore_name, '', next_line)
                                clean_next = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', clean_next).strip()
                                if len(clean_next) >= 2: 
                                    ad = clean_next
                                    break
                                continue
                            clean_next = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', next_line).strip()
                            if len(clean_next) >= 2:
                                ad = clean_next
                                break

            if (not soyad or not ad) and kimlik_bilgileri.get("tc_kimlik"):
                tc_index = -1
                for idx, l in enumerate(lines):
                    if kimlik_bilgileri["tc_kimlik"] in l: tc_index = idx; break
                if tc_index != -1:
                    potansiyel_isimler = []
                    for j in range(tc_index + 1, min(tc_index + 7, len(lines))):
                        l_upper = lines[j].upper()
                        if re.search(r'\d{2}\.\d{2}\.\d{4}', l_upper) or re.search(r'\b(TUR|TC)\b', l_upper): continue
                        if re.search(ignore_surname, l_upper) or re.search(ignore_name, l_upper): continue
                        temiz_metin = re.sub(r'[^A-ZÇĞİÖŞÜ\s]', '', l_upper).strip()
                        if len(temiz_metin) >= 2 and temiz_metin not in ["EM", "KF", "ERKEK", "KADIN"]:
                            potansiyel_isimler.append(temiz_metin)
                    
                    if not soyad and len(potansiyel_isimler) >= 1: soyad = potansiyel_isimler[0]
                    if not ad and len(potansiyel_isimler) >= 2: ad = potansiyel_isimler[1]
                        
            kimlik_bilgileri["ad"] = ad
            kimlik_bilgileri["soyad"] = soyad

            arka_yuz_bilgileri = parse_id_back_side(lines)
            if arka_yuz_bilgileri["anne_adi"]: kimlik_bilgileri["anne_adi"] = arka_yuz_bilgileri["anne_adi"]
            if arka_yuz_bilgileri["baba_adi"]: kimlik_bilgileri["baba_adi"] = arka_yuz_bilgileri["baba_adi"]
            
            if arka_yuz_bilgileri["mrz_data"]:
                mrz = arka_yuz_bilgileri["mrz_data"]
                kimlik_bilgileri["mrz_data"] = mrz
                if not kimlik_bilgileri["ad"] or (mrz.get("ad") and not is_consonant_match(kimlik_bilgileri["ad"], mrz.get("ad"))): kimlik_bilgileri["ad"] = mrz.get("ad", "")
                if not kimlik_bilgileri["soyad"] or (mrz.get("soyad") and not is_consonant_match(kimlik_bilgileri["soyad"], mrz.get("soyad"))): kimlik_bilgileri["soyad"] = mrz.get("soyad", "")
                if not kimlik_bilgileri["tc_kimlik"]: kimlik_bilgileri["tc_kimlik"] = mrz.get("tc_kimlik", "")
                if not kimlik_bilgileri["cinsiyet"]: kimlik_bilgileri["cinsiyet"] = mrz.get("cinsiyet", "")
                if not kimlik_bilgileri["seri_no"]: kimlik_bilgileri["seri_no"] = mrz.get("seri_no", "")
                if not kimlik_bilgileri["dogum_tarihi"]: kimlik_bilgileri["dogum_tarihi"] = mrz.get("dogum_tarihi", "")
                if not kimlik_bilgileri["son_gecerlilik"]: kimlik_bilgileri["son_gecerlilik"] = mrz.get("son_gecerlilik", "")

            response_data = kimlik_bilgileri
            
        # ==========================================
        # BİNİŞ KARTI (BOARDING PASS) OKUMA AKIŞI
        # ==========================================
        elif doc_type == 'boarding_pass':
            response_data = parse_boarding_pass(lines, full_text)

        _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        roi_b64 = base64.b64encode(buffer).decode('utf-8')

        emit('result', {
            'success': True,
            'doc_type': doc_type,
            'extracted_data': response_data,
            'cropped_image': roi_b64
        })
        
    except Exception as e:
        print(f"Sunucu Hatası: {e}")
        import traceback
        traceback.print_exc()
        emit('result', {'error': str(e)})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)