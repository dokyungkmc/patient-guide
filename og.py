"""카톡 미리보기 이미지(og/<부위>.png) 생성. 맥: uv run --with pillow python og.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
FONTS = ["/System/Library/Fonts/AppleSDGothicNeo.ttc", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]
font = next(f for f in FONTS if Path(f).exists())
F = lambda size, idx=0: ImageFont.truetype(font, size, index=idx)
R = [("lumbar", "허리"), ("pelvis", "골반·엉덩이"), ("cervical", "목"), ("shoulder", "어깨"), ("knee", "무릎"), ("wrist_ankle", "손목·발목")]
out = Path(__file__).parent / "og"; out.mkdir(exist_ok=True)
for code, name in R:
    im = Image.new("RGB", (800, 400), "#203a32"); d = ImageDraw.Draw(im)
    d.text((64, 82), "도경한의원 · 진료 후 안내", font=F(26), fill="#c9d6d0")
    d.text((64, 130), name, font=F(64, 6 if font.endswith("Neo.ttc") else 0), fill="#f2f6f4")
    d.text((64, 207), "생활 안내", font=F(64, 6 if font.endswith("Neo.ttc") else 0), fill="#f2f6f4")
    d.text((64, 300), "회복 과정 · 생활 관리 · 재활운동", font=F(26), fill="#a9d8c8")
    im.save(out / f"{code}.png", optimize=True)
print("og 이미지 6장 생성")
