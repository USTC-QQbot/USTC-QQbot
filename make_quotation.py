from PIL import Image, ImageDraw, ImageFont
from io  import BytesIO


WIDTH, HEIGHT = 1536, 512
FONT_SIZE = 120
FONT = ImageFont.truetype("./data/HYLinFengTiW.ttf", size=FONT_SIZE)
PADDING = 30
result = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
draw = ImageDraw.Draw(result)


def auto_split(text: str, max_length: int) -> str:
    length_sum = 0
    todo = []
    for i, c in enumerate(text):
        if c != '\n':
            char_len = draw.textlength(c, font=FONT)
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


def make_quotation(head: bytes, saying, author: str) -> Image.Image:
    global draw, result
    result = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(result)
    head = Image.open(BytesIO(head))
    head = head.resize((HEIGHT, HEIGHT))
    result.paste(head, (0, 0))

    if isinstance(saying, str):
        saying = auto_split(saying, WIDTH - HEIGHT - 2 * PADDING)
        if saying.count('\n') >= 4:
            raise ValueError("句子过长！")
        draw.text((HEIGHT + PADDING, PADDING), saying, fill="white", font=FONT)
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
    w = draw.textlength(author, font=FONT)
    draw.text(
        (WIDTH - w - PADDING, HEIGHT - FONT_SIZE - PADDING),
        author,
        fill="white",
        font=FONT,
    )

    return result
