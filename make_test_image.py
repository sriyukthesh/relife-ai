from PIL import Image, ImageDraw
import io

img = Image.new("RGB", (400, 300), "black")
draw = ImageDraw.Draw(img)
draw.rectangle([50, 50, 150, 100], fill="red", outline="white")
draw.rectangle([200, 100, 280, 150], fill="blue", outline="white")
draw.ellipse([100, 150, 160, 210], fill="green", outline="white")
draw.rectangle([250, 200, 350, 280], fill="yellow", outline="white")

with open(r"C:\Users\sri yukthesh\Downloads\secondlife-ai-phase1\test_components.jpg", "wb") as f:
    img.save(f, format="JPEG", quality=85)

print("Test image saved: test_components.jpg")