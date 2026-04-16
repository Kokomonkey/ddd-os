"""Run once to create PNG icons for the PWA manifest.
Usage: pip install Pillow && python generate_icons.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

os.makedirs('static/icons', exist_ok=True)

WINDOWS_FONTS = [
    'C:/Windows/Fonts/arialbd.ttf',
    'C:/Windows/Fonts/arial.ttf',
    'C:/Windows/Fonts/calibrib.ttf',
]

def get_font(size):
    for path in WINDOWS_FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()

for px in [192, 512]:
    img = Image.new('RGBA', (px, px), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    radius = px // 6
    draw.rounded_rectangle([0, 0, px - 1, px - 1], radius=radius, fill='#16213e')
    draw.rounded_rectangle([px // 12, px // 12, px - px // 12, px - px // 12],
                           radius=radius - 6, fill='#0f3460')

    accent_r = px // 10
    draw.ellipse([px * 7 // 10, px // 10, px * 9 // 10, px * 3 // 10],
                 fill='#0984e3')

    font = get_font(int(px * 0.58))
    bbox = draw.textbbox((0, 0), 'D', font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (px - w) // 2 - bbox[0]
    y = (px - h) // 2 - bbox[1] + int(px * 0.03)
    draw.text((x, y), 'D', fill='white', font=font)

    out = f'static/icons/icon-{px}.png'
    img.save(out, 'PNG')
    print(f'✓  {out}')

print('Done! Icons ready for the PWA manifest.')
