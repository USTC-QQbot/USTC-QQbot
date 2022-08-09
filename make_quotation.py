from PIL import Image, ImageDraw, ImageFont
from io  import BytesIO
from os import listdir
from random import choice


WIDTH, HEIGHT = 1536, 512
FONT_SIZE = 120
FONTS = [ImageFont.truetype("./data/" + fname, size=FONT_SIZE) for fname in listdir("./data/") if fname.endswith(".ttf")]
PADDING = 30
result = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
draw = ImageDraw.Draw(result)


def auto_split(text: str, max_length: int, font) -> str:
    length_sum = 0
    todo = []
    for i, c in enumerate(text):
        if c != '\n':
            char_len = draw.textlength(c, font=font)
            length_sum += char_len
            if length_sum > max_length:
                length_sum = char_len
                todo.append(i)
        else:
            length_sum = 0
    todo.reverse()
    for i in todo:
        text = text[:i] + "\n" + text[i:]
    return text


def make_quotation(head_data: bytes, saying, author: str) -> Image.Image:
    global draw, result
    font = choice(FONTS)
    result = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(result)
    head = Image.open(BytesIO(head_data))
    head = head.resize((HEIGHT, HEIGHT))
    result.paste(head, (0, 0))

    if isinstance(saying, str):
        saying = auto_split(saying, WIDTH - HEIGHT - 2 * PADDING, font)
        if saying.count('\n') >= 4:
            raise ValueError("句子过长！")
        draw.text((HEIGHT + PADDING, PADDING), saying, fill="white", font=font)
    elif isinstance(saying, bytes):
        pic = Image.open(BytesIO(saying))
        size = pic.size
        max_size = (1024 - PADDING, 362)
        if size[0] / size[1] > max_size[0] / max_size[1]:
            scale = max_size[0] / size[0]
        else:
            scale = max_size[1] / size[1]
        pic = pic.resize((int(size[0] * scale), int(size[1] * scale)))
        result.paste(pic, (512 + PADDING, 0))


    author = "--" + author
    w = draw.textlength(author, font=font)
    draw.text(
        (WIDTH - w - PADDING, HEIGHT - FONT_SIZE - PADDING),
        author,
        fill="white",
        font=font,
    )
    head.close()
    return result
