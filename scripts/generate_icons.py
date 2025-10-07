# generate_icons.py
# ✅ Updated to generate confidence-based badges/icons for OCR results

import os
from PIL import Image, ImageDraw, ImageFont

# Output folder relative to this script
output_folder = os.path.join(os.path.dirname(__file__), '../static/images')
os.makedirs(output_folder, exist_ok=True)

def save_image(img, filename):
    path = os.path.join(output_folder, filename)
    img.save(path)
    print(f"Saved {filename} at {path}")

# Basic icons
def create_tick():
    img = Image.new('RGB', (40, 40), color='white')
    draw = ImageDraw.Draw(img)
    draw.line((10, 20, 20, 30), fill="green", width=3)
    draw.line((20, 30, 30, 10), fill="green", width=3)
    save_image(img, 'tick.png')

def create_cross():
    img = Image.new('RGB', (40, 40), color='white')
    draw = ImageDraw.Draw(img)
    draw.line((10, 10, 30, 30), fill="red", width=3)
    draw.line((10, 30, 30, 10), fill="red", width=3)
    save_image(img, 'cross.png')

def create_half_tick():
    img = Image.new('RGB', (40, 40), color='white')
    draw = ImageDraw.Draw(img)
    draw.line((10, 20, 30, 20), fill="orange", width=3)
    save_image(img, 'half_tick.png')

def create_feedback_highlight():
    img = Image.new('RGB', (40, 40), color='yellow')
    save_image(img, 'feedback_highlight.png')

def create_manual_override():
    img = Image.new('RGB', (40, 40), color='blue')
    save_image(img, 'manual_override.png')

def create_marked_background():
    img = Image.new('RGB', (200, 200), color='lightgray')
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 190, 190], outline="black", width=5)
    save_image(img, 'marked_background.png')

# ===== New: Confidence-based icons =====
def create_confidence_icon(confidence: float, filename: str):
    """
    Generate a confidence badge:
    - Green: >=0.8
    - Orange: 0.5-0.8
    - Red: <0.5
    """
    if confidence >= 0.8:
        color = "green"
    elif confidence >= 0.5:
        color = "orange"
    else:
        color = "red"

    img = Image.new('RGB', (60, 60), color='white')
    draw = ImageDraw.Draw(img)
    draw.ellipse([5, 5, 55, 55], fill=color, outline="black", width=2)

    # Optional: overlay confidence as text
    try:
        font = ImageFont.load_default()
        text = f"{int(confidence*100)}%"
        w, h = draw.textsize(text, font=font)
        draw.text(((60-w)/2, (60-h)/2), text, fill="white", font=font)
    except Exception:
        pass  # fallback if font fails

    save_image(img, filename)

# Example usage
if __name__ == '__main__':
    create_tick()
    create_cross()
    create_half_tick()
    create_feedback_highlight()
    create_manual_override()
    create_marked_background()

    # Example confidence icons
    create_confidence_icon(0.9, 'confidence_high.png')
    create_confidence_icon(0.65, 'confidence_medium.png')
    create_confidence_icon(0.3, 'confidence_low.png')
