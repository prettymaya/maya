"""
Translator
==========
cards_data.json'daki kelimeleri Türkçeye çevirir ve JSON'a ekler.
GitHub Pages'de çalışması için çeviriler build-time'da yapılır.

Kullanım:
    .venv/bin/python translate.py
"""

import json
import time
from pathlib import Path
from deep_translator import GoogleTranslator


def translate_word(word: str, translator: GoogleTranslator) -> str:
    """Kelimeyi/ifadeyi Türkçeye çevirir."""
    try:
        result = translator.translate(word.lower())
        return result if result else word
    except Exception as e:
        print(f"  ⚠️  Çeviri hatası '{word}': {e}")
        return ""


def main():
    script_dir = Path(__file__).parent
    data_file = script_dir / "cards_data.json"
    
    if not data_file.exists():
        print("❌ cards_data.json bulunamadı! Önce crop_cards.py çalıştırın.")
        return
    
    with open(data_file, "r", encoding="utf-8") as f:
        cards = json.load(f)
    
    print(f"📝 {len(cards)} kart çevrilecek...\n")
    
    translator = GoogleTranslator(source='en', target='tr')
    
    # Batch çeviri - aynı kelimeleri tekrar çevirme
    unique_words = list(set(card["text"] for card in cards))
    translations = {}
    
    for i, word in enumerate(unique_words, 1):
        if i % 20 == 0:
            print(f"  [{i}/{len(unique_words)}] çevrildi...")
        
        tr = translate_word(word, translator)
        translations[word] = tr
        
        # Rate limit - çok hızlı gitme
        if i % 50 == 0:
            time.sleep(1)
    
    # Çevirileri kartlara ekle
    for card in cards:
        card["tr"] = translations.get(card["text"], "")
    
    # JSON'ı kaydet
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(cards, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*50}")
    print(f"✅ {len(unique_words)} benzersiz kelime çevrildi")
    print(f"📄 Güncellenmiş: {data_file}")
    print(f"{'='*50}")
    
    # Birkaç örnek göster
    print("\n📋 Örnek çeviriler:")
    examples = [c for c in cards if len(c["text"].split()) > 2][:5]
    if not examples:
        examples = cards[:5]
    for card in examples:
        print(f"  {card['text']} → {card.get('tr', '?')}")


if __name__ == "__main__":
    main()
