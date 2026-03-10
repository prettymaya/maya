"""
Image to Text Extractor
=======================
Klasördeki tüm fotoğraflardan metinleri çıkarır ve bir liste oluşturur.
Her 50 kelimeden sonra sayfa numarası koyar (ör: --- 17/1 ---)
macOS Vision framework kullanır.

Kurulum:
    python3 -m venv .venv
    .venv/bin/pip install pyobjc-framework-Vision pyobjc-framework-Quartz

Kullanım:
    .venv/bin/python extract.py
"""

import os
import sys
import re
import glob
import math
from pathlib import Path

import Vision
import Quartz
from Foundation import NSURL


def extract_text_from_image(image_path: str) -> list[str]:
    """Bir fotoğraftan tüm metinleri çıkarır (macOS Vision OCR).
    
    Yakın y-koordinatlarındaki satırları birleştirir,
    böylece çok satırlı ifadeler bölünmez.
    """
    
    image_url = NSURL.fileURLWithPath_(image_path)
    ci_image = Quartz.CIImage.imageWithContentsOfURL_(image_url)
    if ci_image is None:
        print(f"  ⚠️  Resim yüklenemedi: {image_path}")
        return []
    
    handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["en"])
    request.setUsesLanguageCorrection_(True)
    
    success, error = handler.performRequests_error_([request], None)
    if not success:
        print(f"  ⚠️  OCR hatası: {error}")
        return []
    
    # Her observation'ın pozisyon bilgisini ve metnini al
    observations = []
    for obs in request.results():
        text = obs.topCandidates_(1)[0].string().strip()
        if not text:
            continue
        bbox = obs.boundingBox()
        center_x = bbox.origin.x + bbox.size.width / 2
        center_y = bbox.origin.y + bbox.size.height / 2
        observations.append({
            "text": text,
            "x": center_x,
            "y": center_y,
            "height": bbox.size.height,
            "width": bbox.size.width,
            "min_x": bbox.origin.x,
            "max_x": bbox.origin.x + bbox.size.width,
        })
    
    if not observations:
        return []
    
    # Sütunları belirle (3 sütunlu layout)
    observations.sort(key=lambda o: o["min_x"])
    
    # X ekseninde kümeleme
    columns = []
    for obs in observations:
        placed = False
        for col in columns:
            col_center = sum(o["x"] for o in col) / len(col)
            if abs(obs["x"] - col_center) < 0.15:
                col.append(obs)
                placed = True
                break
        if not placed:
            columns.append([obs])
    
    # Sütunları soldan sağa sırala
    columns.sort(key=lambda col: sum(o["x"] for o in col) / len(col))
    
    # Her sütun içinde y'ye göre sırala ve yakın olanları birleştir
    results = []
    for col in columns:
        col.sort(key=lambda o: -o["y"])  # Yukarıdan aşağıya
        
        i = 0
        while i < len(col):
            current = col[i]
            merged_text = current["text"]
            
            j = i + 1
            while j < len(col):
                next_obs = col[j]
                y_gap = abs(current["y"] - next_obs["y"])
                if y_gap < 0.06:
                    merged_text += " " + next_obs["text"]
                    current = next_obs
                    j += 1
                else:
                    break
            
            results.append(merged_text.strip())
            i = j
    
    return results


def clean_text(text: str) -> str:
    """Metni temizle."""
    text = text.strip()
    text = text.rstrip(":.")
    # OCR'ın emojilerden okuduğu sondaki tek harfleri kaldır (ör: "CIRCUS O" -> "CIRCUS")
    text = re.sub(r'\s+[A-Za-z]$', '', text)
    text = text.upper()
    return text


def main():
    script_dir = Path(__file__).parent
    
    extensions = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.tiff"]
    
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(str(script_dir / ext)))
    image_files.sort()
    
    if not image_files:
        print("❌ Klasörde resim dosyası bulunamadı!")
        sys.exit(1)
    
    print(f"📸 {len(image_files)} resim bulundu.\n")
    
    all_words = []
    
    for i, img_path in enumerate(image_files, 1):
        filename = os.path.basename(img_path)
        print(f"[{i}/{len(image_files)}] İşleniyor: {filename}")
        
        texts = extract_text_from_image(img_path)
        
        if texts:
            for text in texts:
                cleaned = clean_text(text)
                if cleaned:
                    all_words.append(cleaned)
            print(f"  ✅ {len(texts)} kelime/ifade çıkarıldı")
        else:
            print(f"  ⚠️  Metin bulunamadı")
    
    # Tekrar edenleri kaldır (sırayı koru)
    seen = set()
    unique_words = []
    for word in all_words:
        if word not in seen:
            seen.add(word)
            unique_words.append(word)
    
    # Toplam sayfa sayısını hesapla
    total_pages = math.ceil(len(unique_words) / 50)
    
    # Dosyaya yaz - her 50 kelimede bir ayırıcı koy
    output_file = script_dir / "word_list_ocr.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        word_count = 0
        page = 1
        
        for word in unique_words:
            # Her 50 kelimede bir ayırıcı koy (başta değil, her grubun sonunda)
            if word_count > 0 and word_count % 50 == 0:
                f.write(f"\n--- {total_pages}/{page} ---\n\n")
                page += 1
            
            f.write(word + "\n")
            word_count += 1
        
        # Son grubun etiketini de koy
        if word_count % 50 != 0:
            f.write(f"\n--- {total_pages}/{page} ---\n")
    
    print(f"\n{'='*50}")
    print(f"✅ Toplam çıkarılan: {len(all_words)} kelime/ifade")
    print(f"✅ Benzersiz (yazılan): {len(unique_words)} kelime/ifade")
    print(f"📑 Sayfa sayısı: {total_pages} ({total_pages-1}x50 + {len(unique_words) - (total_pages-1)*50})")
    print(f"📄 Sonuç: {output_file}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
