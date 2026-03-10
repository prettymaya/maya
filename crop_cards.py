"""
Card Cropper + OCR
==================
Fotoğrafları matematiksel grid ile 3x8 = 24 karta böler.
Her kartı OCR ile okur, cards/ klasörüne kaydeder.
Ayrıca word_list_ocr.txt ve cards_data.json oluşturur.

Tüm fotoğraflar 1130x934 piksel, 3 sütun x 8 satır grid.

Kullanım:
    .venv/bin/python crop_cards.py
"""

import os
import json
import glob
import re
import math
from pathlib import Path

from PIL import Image

import Vision
import Quartz
from Foundation import NSURL


# Grid yapısı (tüm fotoğraflar için sabit)
# Boşluk koordinatları analiz sonucu:
# Yatay boşluklar: y=0-6, 116-123, 233-240, 350-358, 467-475, 584-592, 701-709, 818-826, 926-933
# Dikey boşluklar: x=0-14, 375-383, 743-751, 1112-1129

COLS = [
    (15, 374),    # Sütun 1
    (384, 742),   # Sütun 2
    (752, 1111),  # Sütun 3
]

ROWS = [
    (7, 115),     # Satır 1
    (124, 232),   # Satır 2
    (241, 349),   # Satır 3
    (359, 466),   # Satır 4
    (476, 583),   # Satır 5
    (593, 700),   # Satır 6
    (710, 817),   # Satır 7
    (827, 925),   # Satır 8
]

CARDS_PER_IMAGE = len(ROWS) * len(COLS)  # 24


def get_card_regions() -> list[dict]:
    """Grid koordinatlarından kart bölgelerini döndürür. Satır satır, soldan sağa."""
    cards = []
    for row_top, row_bottom in ROWS:
        for col_left, col_right in COLS:
            cards.append({
                "x": col_left,
                "y": row_top,
                "w": col_right - col_left + 1,
                "h": row_bottom - row_top + 1
            })
    return cards


def extract_text_from_image(img_path: str) -> str:
    """Bir bölge resminden OCR ile metin çıkarır."""
    image_url = NSURL.fileURLWithPath_(img_path)
    ci_image = Quartz.CIImage.imageWithContentsOfURL_(image_url)
    if ci_image is None:
        return ""
    
    handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["en"])
    request.setUsesLanguageCorrection_(True)
    
    success, error = handler.performRequests_error_([request], None)
    if not success:
        return ""
    
    texts = []
    for obs in request.results():
        text = obs.topCandidates_(1)[0].string().strip()
        if text:
            texts.append(text)
    
    result = " ".join(texts).strip()
    # Trailing single char cleanup (emoji OCR artifacts)
    result = re.sub(r'\s+[A-Za-z]$', '', result)
    result = result.rstrip(":.")
    
    return result.upper()


def main():
    script_dir = Path(__file__).parent
    cards_dir = script_dir / "cards"
    cards_dir.mkdir(exist_ok=True)
    
    # Eski kartları temizle
    for old_card in cards_dir.glob("card_*.png"):
        old_card.unlink()
    
    # Sadece Screenshot dosyalarını al (icon.png gibi dosyaları atlayarak)
    image_files = sorted(glob.glob(str(script_dir / "Screenshot*.png")))
    
    if not image_files:
        print("❌ Klasörde Screenshot dosyası bulunamadı!")
        return
    
    print(f"📸 {len(image_files)} fotoğraf bulundu")
    print(f"📐 Grid: {len(COLS)}x{len(ROWS)} = {CARDS_PER_IMAGE} kart/fotoğraf")
    print(f"📊 Beklenen toplam: {len(image_files) * CARDS_PER_IMAGE} kart\n")
    
    regions = get_card_regions()
    all_cards = []
    all_words = []
    card_index = 0
    tmp_path = "/tmp/_ocr_temp_card.png"
    
    for i, img_path in enumerate(image_files, 1):
        filename = os.path.basename(img_path)
        print(f"[{i}/{len(image_files)}] {filename}")
        
        img = Image.open(img_path)
        img_w, img_h = img.size
        
        for region in regions:
            card_index += 1
            
            # Kartı kırp (resim sınırlarını aşmamaya dikkat et)
            x1 = min(region["x"], img_w)
            y1 = min(region["y"], img_h)
            x2 = min(region["x"] + region["w"], img_w)
            y2 = min(region["y"] + region["h"], img_h)
            
            card_img = img.crop((x1, y1, x2, y2))
            
            # Geçici dosyaya kaydet, OCR yap
            card_img.save(tmp_path, "PNG")
            text = extract_text_from_image(tmp_path)
            
            if not text:
                text = f"CARD_{card_index}"
            
            # Dosya adı oluştur
            safe_name = text.lower().replace(" ", "_").replace("'", "")
            safe_name = re.sub(r'[^a-z0-9_]', '', safe_name)[:40]
            card_filename = f"card_{card_index:03d}_{safe_name}.png"
            
            # Kartı kaydet
            card_path = cards_dir / card_filename
            card_img.save(str(card_path), "PNG")
            
            all_cards.append({
                "file": card_filename,
                "text": text,
                "index": card_index
            })
            
            all_words.append(text)
        
        print(f"  ✅ {CARDS_PER_IMAGE} kart kesildi")
    
    # Geçici dosyayı temizle
    try:
        os.remove(tmp_path)
    except:
        pass
    
    # --- JSON veri dosyası (viewer için) ---
    data_file = script_dir / "cards_data.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(all_cards, f, ensure_ascii=False, indent=2)
    
    # --- word_list_ocr.txt (50'li gruplar) ---
    unique_words = list(dict.fromkeys(all_words))  # Sırayı koruyarak unique yap
    
    total_pages = math.ceil(len(unique_words) / 50)
    
    txt_file = script_dir / "word_list_ocr.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        for page in range(total_pages):
            start = page * 50
            end = min(start + 50, len(unique_words))
            
            for word in unique_words[start:end]:
                f.write(word + "\n")
            
            f.write(f"\n--- {total_pages}/{page + 1} ---\n\n")
    
    print(f"\n{'='*50}")
    print(f"✅ Toplam {card_index} kart kesildi ve kaydedildi")
    print(f"✅ {len(all_words)} toplam kelime çıkarıldı")
    print(f"✅ {len(unique_words)} benzersiz kelime yazıldı")
    print(f"📑 Sayfa: {total_pages} ({total_pages-1}x50 + {len(unique_words) - (total_pages-1)*50})")
    print(f"📁 Kartlar: {cards_dir}/")
    print(f"📄 JSON: {data_file}")
    print(f"📄 TXT: {txt_file}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
