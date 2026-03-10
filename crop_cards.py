"""
Card Cropper
=============
Fotoğraflardaki mavi kutucukları (kartları) tek tek keser ve kaydeder.
Ayrıca viewer.html için gerekli JSON verisini oluşturur.

Kullanım:
    .venv/bin/python crop_cards.py
"""

import os
import json
import glob
import re
from pathlib import Path

import numpy as np
from PIL import Image

import Vision
import Quartz
from Foundation import NSURL


def detect_card_regions(image_path: str) -> list[dict]:
    """Fotoğraftaki kart bölgelerini tespit eder.
    Hem mavi hem yeşil kartları yakalar.
    """
    img = Image.open(image_path)
    arr = np.array(img)
    
    r, g, b = arr[:,:,0].astype(int), arr[:,:,1].astype(int), arr[:,:,2].astype(int)
    
    # Mavi kart maskesi
    blue_mask = (b > 100) & (b > r + 15) & (r < 180) & (g < 180)
    
    # Yeşil kart maskesi
    green_mask = (g > 100) & (g > r) & (g > b - 30) & (r < 180)
    
    # Birleşik maske
    card_mask = (blue_mask | green_mask).astype(np.uint8)
    
    h, w = card_mask.shape
    
    # Yatay projeksiyon
    h_proj = np.sum(card_mask, axis=1)
    h_threshold = w * 0.10
    
    # Satır bölgelerini bul
    in_row = False
    row_regions = []
    row_start = 0
    
    for y in range(h):
        if h_proj[y] > h_threshold and not in_row:
            in_row = True
            row_start = y
        elif h_proj[y] <= h_threshold and in_row:
            in_row = False
            row_h = y - row_start
            if row_h > 15:
                row_regions.append((row_start, y))
    
    if in_row:
        row_h = h - row_start
        if row_h > 15:
            row_regions.append((row_start, h))
    
    # Her satır içinde sütunları bul
    cards = []
    
    for row_top, row_bottom in row_regions:
        row_slice = card_mask[row_top:row_bottom, :]
        v_proj = np.sum(row_slice, axis=0)
        v_threshold = (row_bottom - row_top) * 0.10
        
        in_col = False
        col_start = 0
        
        for x in range(w):
            if v_proj[x] > v_threshold and not in_col:
                in_col = True
                col_start = x
            elif v_proj[x] <= v_threshold and in_col:
                in_col = False
                col_w = x - col_start
                if col_w > 50:
                    cards.append({
                        "x": col_start,
                        "y": row_top,
                        "w": col_w,
                        "h": row_bottom - row_top
                    })
        
        if in_col:
            col_w = w - col_start
            if col_w > 50:
                cards.append({
                    "x": col_start,
                    "y": row_top,
                    "w": col_w,
                    "h": row_bottom - row_top
                })
    
    cards.sort(key=lambda c: (c["y"], c["x"]))
    
    return cards


def extract_text_from_region(image_path: str, region: dict) -> str:
    """Belirli bir bölgedeki metni OCR ile çıkarır."""
    img = Image.open(image_path)
    cropped = img.crop((
        region["x"], region["y"],
        region["x"] + region["w"],
        region["y"] + region["h"]
    ))
    
    tmp_path = "/tmp/_ocr_temp_card.png"
    cropped.save(tmp_path)
    
    image_url = NSURL.fileURLWithPath_(tmp_path)
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
    result = re.sub(r'\s+[A-Za-z]$', '', result)
    result = result.rstrip(":.")
    
    try:
        os.remove(tmp_path)
    except:
        pass
    
    return result.upper()


def main():
    script_dir = Path(__file__).parent
    cards_dir = script_dir / "cards"
    cards_dir.mkdir(exist_ok=True)
    
    # Eski kartları temizle
    for old_card in cards_dir.glob("card_*.png"):
        old_card.unlink()
    
    extensions = ["*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.tiff"]
    
    image_files = []
    for ext in extensions:
        image_files.extend(glob.glob(str(script_dir / ext)))
    image_files.sort()
    
    if not image_files:
        print("❌ Klasörde resim dosyası bulunamadı!")
        return
    
    print(f"📸 {len(image_files)} resim bulundu.\n")
    
    all_cards = []
    card_index = 0
    
    for i, img_path in enumerate(image_files, 1):
        filename = os.path.basename(img_path)
        print(f"[{i}/{len(image_files)}] İşleniyor: {filename}")
        
        img = Image.open(img_path)
        regions = detect_card_regions(img_path)
        print(f"  📦 {len(regions)} kart tespit edildi")
        
        for region in regions:
            card_index += 1
            
            card_img = img.crop((
                region["x"], region["y"],
                region["x"] + region["w"],
                region["y"] + region["h"]
            ))
            
            text = extract_text_from_region(img_path, region)
            
            if not text:
                text = f"CARD_{card_index}"
            
            safe_name = text.lower().replace(" ", "_").replace("'", "")
            safe_name = re.sub(r'[^a-z0-9_]', '', safe_name)
            card_filename = f"card_{card_index:03d}_{safe_name}.png"
            
            card_path = cards_dir / card_filename
            card_img.save(str(card_path), "PNG")
            
            all_cards.append({
                "file": card_filename,
                "text": text,
                "index": card_index
            })
        
        print(f"  ✅ {len(regions)} kart kaydedildi")
    
    # JSON veri dosyası
    data_file = script_dir / "cards_data.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(all_cards, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"✅ Toplam {card_index} kart kesildi ve kaydedildi")
    print(f"📁 Kartlar: {cards_dir}/")
    print(f"📄 Veri: {data_file}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
