from requests import get
from re import search


def valid(qq, code):
    r = get(f'https://qq.ustc.life/p/{code}', allow_redirects=True)
    r.encoding = 'utf-8'
    if r.url == 'https://qq.ustc.life/':
        return False
    m = search(r"QQ 号：(\d+)", r.text)
    if m:
        qq_ = m.groups()[0]
        return (str(qq) == qq_)
    else:
        print(f'Unexpected result at code {code}.')
        print(r.url)
        return False
