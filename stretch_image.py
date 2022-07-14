from PIL import Image, ImageDraw, ImageFont


HEIGHT = 200
FIX = 26
FONT = ImageFont.truetype("./data/微软雅黑.ttf", size=HEIGHT + FIX, encoding="utf-8")
def make_stretch_image(text):
    WIDTH = int(FONT.getlength(text)) + 1
    img = Image.new("RGB", (WIDTH, HEIGHT), "white")
    draw = ImageDraw.Draw(img)
    draw.text((0, -2*FIX), text, fill="black", font=FONT)
    img = img.resize((WIDTH // 4, HEIGHT * 8))
    return img

if __name__ == "__main__":
    make_stretch_image("肯德基疯狂星期四 富哥V50").save('test.jpg')
