from requests import get
from re import search
from os.path import exists


def valid(qq: int, code: str, group: int):
    r = get(f'https://qq.ustc.life/p/{code}', allow_redirects=True)
    r.encoding = 'utf-8'
    if r.url == 'https://qq.ustc.life/':
        return False
    m = search(r"QQ 号：(\d+)", r.text)
    n = search(r"学号（或教工号）：(.+\d+)", r.text)
    if m and n:
        qq_ = m.groups()[0]
        stu_id = n.groups()[0]
        return (str(qq) == qq_) and valid_id(qq, stu_id, group)
    else:
        print(f'Unexpected result with code {code}.')
        print(r.url)
        return False

def valid_id(qq: int, stu_id: str, group: int):
    path = f"./data/ids/{group}.txt"
    if exists(path):
        with open(path) as f:
            joined = f.read()
    else:
        joined = ''
    if (not "*" in stu_id) and (not (":" + stu_id) in joined):
        flag = True
        joined += f"{qq}:{stu_id}\n"
    else:
        flag = False
    with open(path, 'w') as f:
        f.write(joined)
    return flag
