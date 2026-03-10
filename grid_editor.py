"""
Grid Editor
============
Görsel grid editörü. Tarayıcıda fotoğrafları gösterir,
grid çizgilerini slider'larla ayarlarsın, A tuşuyla işlersin.

Kullanım:
    .venv/bin/python grid_editor.py
    Tarayıcıda otomatik açılır: http://localhost:8765
    
İşlem bittikten sonra:
    .venv/bin/python translate.py   (Türkçe çeviri ekler)
"""

import os
import json
import re
import math
import glob
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import urllib.parse

from PIL import Image

import Vision
import Quartz
from Foundation import NSURL

SCRIPT_DIR = Path(__file__).parent
CARDS_DIR = SCRIPT_DIR / "cards"
IMAGE_FILES = []
ALL_CARDS = []
CARD_INDEX = 0


def extract_text_from_image(img_path):
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
    result = re.sub(r'\s+[A-Za-z]$', '', result)
    result = result.rstrip(":.")
    return result.upper()


def process_image(img_path, grid):
    global CARD_INDEX
    img = Image.open(img_path)
    img_w, img_h = img.size
    rows, cols = grid["rows"], grid["cols"]
    usable_w = img_w - grid["padLeft"] - grid["padRight"] - (cols - 1) * grid["gapX"]
    usable_h = img_h - grid["padTop"] - grid["padBottom"] - (rows - 1) * grid["gapY"]
    card_w, card_h = usable_w / cols, usable_h / rows
    count = 0
    tmp = "/tmp/_ocr_temp.png"
    for row in range(rows):
        for col in range(cols):
            CARD_INDEX += 1
            x1 = int(grid["padLeft"] + col * (card_w + grid["gapX"]))
            y1 = int(grid["padTop"] + row * (card_h + grid["gapY"]))
            x2, y2 = min(int(x1 + card_w), img_w), min(int(y1 + card_h), img_h)
            card_img = img.crop((x1, y1, x2, y2))
            card_img.save(tmp, "PNG")
            text = extract_text_from_image(tmp)
            if not text:
                text = "CARD_" + str(CARD_INDEX)
            safe = re.sub(r'[^a-z0-9_]', '', text.lower().replace(" ", "_").replace("'", ""))[:40]
            fname = "card_" + str(CARD_INDEX).zfill(3) + "_" + safe + ".png"
            card_img.save(str(CARDS_DIR / fname), "PNG")
            ALL_CARDS.append({"file": fname, "text": text, "index": CARD_INDEX})
            count += 1
    try:
        os.remove(tmp)
    except:
        pass
    return count


def save_results():
    data_file = SCRIPT_DIR / "cards_data.json"
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(ALL_CARDS, f, ensure_ascii=False, indent=2)
    words = [c["text"] for c in ALL_CARDS]
    pages = math.ceil(len(words) / 50)
    txt_file = SCRIPT_DIR / "word_list_ocr.txt"
    with open(txt_file, "w", encoding="utf-8") as f:
        for p in range(pages):
            for w in words[p*50 : min((p+1)*50, len(words))]:
                f.write(w + "\n")
            f.write("\n--- " + str(pages) + "/" + str(p+1) + " ---\n\n")
    print("\n" + "="*50)
    print("Toplam " + str(CARD_INDEX) + " kart")
    print("Dosya: " + str(data_file))
    print("Dosya: " + str(txt_file))
    print("="*50)


EDITOR_PAGE = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Grid Editor</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap" rel="stylesheet">
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Inter',sans-serif; background:#0a0e1a; color:#e0e0e0; overflow:hidden; height:100vh; display:flex; flex-direction:column; }
.top-bar { padding:12px 20px; display:flex; justify-content:space-between; align-items:center; background:rgba(15,20,35,0.95); border-bottom:1px solid rgba(74,122,245,0.15); z-index:10; }
.logo { font-size:14px; font-weight:700; color:#4a7af5; letter-spacing:1px; }
.info { font-size:13px; color:#667799; }
.info span { color:#4a7af5; font-weight:700; }
.main { flex:1; display:flex; position:relative; overflow:hidden; }
.canvas-area { flex:1; position:relative; display:flex; align-items:center; justify-content:center; }
canvas { max-width:100%%; max-height:100%%; cursor:crosshair; }
.sidebar { width:220px; padding:16px; background:rgba(15,20,35,0.95); border-left:1px solid rgba(74,122,245,0.15); overflow-y:auto; display:flex; flex-direction:column; gap:10px; }
.cg { display:flex; flex-direction:column; gap:2px; }
.cg label { font-size:10px; color:#667799; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; }
.cg input[type=range] { width:100%%; accent-color:#4a7af5; }
.cg .v { font-size:11px; color:#4a7af5; font-weight:700; text-align:right; }
.btn { padding:10px; border:none; border-radius:8px; font-family:'Inter',sans-serif; font-size:13px; font-weight:700; cursor:pointer; width:100%%; }
.btn-p { background:#4a7af5; color:white; }
.btn-p:hover { background:#5a8aff; }
.btn-s { background:#28a745; color:white; margin-top:4px; }
.btn-s:hover { background:#34c759; }
.bottom-bar { padding:8px 20px; background:rgba(15,20,35,0.95); border-top:1px solid rgba(74,122,245,0.15); display:flex; justify-content:center; gap:20px; }
.hint { font-size:11px; color:#445566; }
.hint kbd { background:rgba(74,122,245,0.15); border:1px solid rgba(74,122,245,0.2); border-radius:4px; padding:1px 6px; color:#4a7af5; font-weight:700; }
.st { font-size:12px; padding:8px 12px; border-radius:6px; text-align:center; background:rgba(74,122,245,0.1); color:#4a7af5; }
hr { border:none; border-top:1px solid rgba(74,122,245,0.1); }
</style>
</head>
<body>
<div class="top-bar">
  <div class="logo">Grid Editor</div>
  <div class="info">Foto <span id="ci">1</span>/<span id="tc">0</span> | Kart: <span id="cc">0</span></div>
</div>
<div class="main">
  <div class="canvas-area"><canvas id="cv"></canvas></div>
  <div class="sidebar">
    <div class="st" id="st">Grid ayarla, A bas</div>
    <div class="cg"><label>Satir</label><input type="range" id="rows" min="1" max="12" value="8"><div class="v" id="rows-v">8</div></div>
    <div class="cg"><label>Sutun</label><input type="range" id="cols" min="1" max="6" value="3"><div class="v" id="cols-v">3</div></div>
    <hr>
    <div class="cg"><label>Ust</label><input type="range" id="pT" min="0" max="100" value="7"><div class="v" id="pT-v">7</div></div>
    <div class="cg"><label>Alt</label><input type="range" id="pB" min="0" max="100" value="8"><div class="v" id="pB-v">8</div></div>
    <div class="cg"><label>Sol</label><input type="range" id="pL" min="0" max="100" value="15"><div class="v" id="pL-v">15</div></div>
    <div class="cg"><label>Sag</label><input type="range" id="pR" min="0" max="100" value="18"><div class="v" id="pR-v">18</div></div>
    <hr>
    <div class="cg"><label>Sutun Arasi</label><input type="range" id="gX" min="0" max="30" value="9"><div class="v" id="gX-v">9</div></div>
    <div class="cg"><label>Satir Arasi</label><input type="range" id="gY" min="0" max="30" value="9"><div class="v" id="gY-v">9</div></div>
    <hr>
    <button class="btn btn-p" onclick="doProcess()">Isle (A)</button>
    <button class="btn btn-s" onclick="doFinish()" id="fb" style="display:none">Tamamla (Q)</button>
  </div>
</div>
<div class="bottom-bar">
  <div class="hint"><kbd>A</kbd> Isle</div>
  <div class="hint"><kbd>&larr;</kbd><kbd>&rarr;</kbd> Gezin</div>
  <div class="hint"><kbd>Q</kbd> Kaydet</div>
</div>
<script>
var cv=document.getElementById('cv'),cx=cv.getContext('2d');
var imgs=[],ci=0,cimg=null,nw=0,nh=0,tp=0,ps={};
var ids=['rows','cols','pT','pB','pL','pR','gX','gY'];

function init(){
  var x=new XMLHttpRequest();
  x.open('GET','/api/images',true);
  x.onload=function(){
    if(x.status===200){
      imgs=JSON.parse(x.responseText);
      document.getElementById('tc').textContent=imgs.length;
      if(imgs.length>0)loadImg(0);
    }
  };
  x.send();
}

function loadImg(i){
  ci=i;
  document.getElementById('ci').textContent=i+1;
  var im=new Image();
  im.onload=function(){
    cimg=im; nw=im.naturalWidth; nh=im.naturalHeight;
    fitCanvas(); drawGrid();
  };
  im.src='/images/'+encodeURIComponent(imgs[i]);
  var s=document.getElementById('st');
  s.textContent=ps[i]?'Islendi':'Grid ayarla, A bas';
  s.style.color=ps[i]?'#28a745':'#4a7af5';
}

function fitCanvas(){
  var a=cv.parentElement,mw=a.clientWidth-40,mh=a.clientHeight-40;
  var s=Math.min(mw/nw,mh/nh);
  cv.width=Math.floor(nw*s); cv.height=Math.floor(nh*s);
}

function gv(id){return parseInt(document.getElementById(id).value);}

function drawGrid(){
  if(!cimg)return;
  cx.clearRect(0,0,cv.width,cv.height);
  cx.drawImage(cimg,0,0,cv.width,cv.height);
  var sx=cv.width/nw,sy=cv.height/nh;
  var r=gv('rows'),c=gv('cols');
  var t=gv('pT')*sy,b=gv('pB')*sy,l=gv('pL')*sx,ri=gv('pR')*sx;
  var gx=gv('gX')*sx,gy=gv('gY')*sy;
  var uw=cv.width-l-ri-(c-1)*gx, uh=cv.height-t-b-(r-1)*gy;
  var cw=uw/c,ch=uh/r;
  cx.strokeStyle='rgba(255,50,50,0.8)'; cx.lineWidth=1.5;
  cx.fillStyle='rgba(255,50,50,0.9)'; cx.font='bold 10px Inter,sans-serif';
  for(var row=0;row<r;row++){
    for(var col=0;col<c;col++){
      var x=l+col*(cw+gx), y=t+row*(ch+gy);
      cx.strokeRect(x,y,cw,ch);
      cx.fillText(String(row*c+col+1),x+3,y+12);
    }
  }
  cx.fillStyle='rgba(255,255,255,0.6)'; cx.font='10px Inter';
  cx.fillText(r+'x'+c+'='+r*c+' kart',5,cv.height-5);
}

ids.forEach(function(id){
  var el=document.getElementById(id);
  el.addEventListener('input',function(){
    document.getElementById(id+'-v').textContent=el.value;
    drawGrid();
  });
});

function doProcess(){
  if(ci>=imgs.length)return;
  var s=document.getElementById('st');
  s.textContent='Isleniyor...'; s.style.color='#ffa500';
  var g={rows:gv('rows'),cols:gv('cols'),padTop:gv('pT'),padBottom:gv('pB'),padLeft:gv('pL'),padRight:gv('pR'),gapX:gv('gX'),gapY:gv('gY')};
  var x=new XMLHttpRequest();
  x.open('POST','/api/process',true);
  x.setRequestHeader('Content-Type','application/json');
  x.onload=function(){
    var r=JSON.parse(x.responseText);
    ps[ci]=true; tp+=r.cards;
    document.getElementById('cc').textContent=tp;
    s.textContent=r.cards+' kart kesildi'; s.style.color='#28a745';
    setTimeout(function(){
      if(ci<imgs.length-1){loadImg(ci+1);}
      else{document.getElementById('fb').style.display='block';s.textContent='Tum fotograflar islendi!';}
    },400);
  };
  x.send(JSON.stringify({imageIndex:ci,grid:g}));
}

function doFinish(){
  var x=new XMLHttpRequest();
  x.open('POST','/api/finish',true);
  x.onload=function(){
    var r=JSON.parse(x.responseText);
    var s=document.getElementById('st');
    s.textContent=r.totalCards+' kart kaydedildi!'; s.style.color='#28a745';
  };
  x.send();
}

document.addEventListener('keydown',function(e){
  if(e.key==='a'||e.key==='A'){e.preventDefault();doProcess();}
  else if(e.key==='ArrowRight'&&ci<imgs.length-1)loadImg(ci+1);
  else if(e.key==='ArrowLeft'&&ci>0)loadImg(ci-1);
  else if(e.key==='q'||e.key==='Q')doFinish();
});

window.addEventListener('resize',function(){if(cimg){fitCanvas();drawGrid();}});

var dragging=false,dragX=0,dragY=0;
cv.style.cursor='grab';

cv.addEventListener('mousedown',function(e){
  dragging=true; dragX=e.clientX; dragY=e.clientY;
  cv.style.cursor='grabbing';
  e.preventDefault();
});

window.addEventListener('mousemove',function(e){
  if(!dragging||!cimg)return;
  var sx=cv.width/nw, sy=cv.height/nh;
  var dx=Math.round((e.clientX-dragX)/sx);
  var dy=Math.round((e.clientY-dragY)/sy);
  if(dx===0&&dy===0)return;
  dragX=e.clientX; dragY=e.clientY;
  var el,v;
  if(dx!==0){
    el=document.getElementById('pL');
    v=Math.max(0,Math.min(100,parseInt(el.value)+dx));
    el.value=v; document.getElementById('pL-v').textContent=v;
    el=document.getElementById('pR');
    v=Math.max(0,Math.min(100,parseInt(el.value)-dx));
    el.value=v; document.getElementById('pR-v').textContent=v;
  }
  if(dy!==0){
    el=document.getElementById('pT');
    v=Math.max(0,Math.min(100,parseInt(el.value)+dy));
    el.value=v; document.getElementById('pT-v').textContent=v;
    el=document.getElementById('pB');
    v=Math.max(0,Math.min(100,parseInt(el.value)-dy));
    el.value=v; document.getElementById('pB-v').textContent=v;
  }
  drawGrid();
});

window.addEventListener('mouseup',function(){
  if(dragging){dragging=false; cv.style.cursor='grab';}
});

init();
</script>
</body>
</html>
"""


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/editor':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(EDITOR_PAGE.encode('utf-8'))
        elif self.path == '/api/images':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps([os.path.basename(f) for f in IMAGE_FILES]).encode())
        elif self.path.startswith('/images/'):
            fp = SCRIPT_DIR / urllib.parse.unquote(self.path[8:])
            if fp.exists():
                self.send_response(200)
                self.send_header('Content-type', 'image/png')
                self.end_headers()
                with open(fp, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/process':
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
            img_path = IMAGE_FILES[body['imageIndex']]
            print("  Isleniyor: " + os.path.basename(img_path))
            count = process_image(img_path, body['grid'])
            print("  " + str(count) + " kart (toplam: " + str(CARD_INDEX) + ")")
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"cards": count}).encode())
        elif self.path == '/api/finish':
            save_results()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"totalCards": CARD_INDEX, "totalWords": len(ALL_CARDS)}).encode())
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass


def main():
    global IMAGE_FILES
    CARDS_DIR.mkdir(exist_ok=True)
    for old in CARDS_DIR.glob("card_*.png"):
        old.unlink()
    IMAGE_FILES = sorted(glob.glob(str(SCRIPT_DIR / "Screenshot*.png")))
    if not IMAGE_FILES:
        print("Screenshot dosyasi bulunamadi!")
        return
    print(str(len(IMAGE_FILES)) + " fotograf bulundu")
    print("Tarayici aciliyor: http://localhost:8765\n")
    webbrowser.open("http://localhost:8765")
    server = HTTPServer(('', 8765), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDurduruldu")
        if ALL_CARDS:
            save_results()


if __name__ == "__main__":
    main()
