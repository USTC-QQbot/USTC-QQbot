from random import choices
from string import ascii_letters, digits
from time import localtime, strftime, time

from bs4 import BeautifulSoup as bs
from requests import Session
from requests_toolbelt import MultipartEncoder
from re import search
from PIL import Image
from io import BytesIO


def gen_boundary():
    return "----WebKitFormBoundary" + "".join(choices(ascii_letters + digits, k=16))


class Covid:
    def __init__(self, username, password) -> None:
        self.username = username
        self.password = password
        self.session = Session()
        self.jid = "".join(choices(ascii_letters + digits, k=32)).upper()
        self.session.cookies.update({"JSESSIONID": self.jid, "lang": "zh"})
        self.session.headers = {
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "sec-ch-ua": '"Chromium";v="94", "Microsoft Edge";v="94", ";Not A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Origin": "https://passport.ustc.edu.cn",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36 Edg/94.0.992.50",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Referer": "https://passport.ustc.edu.cn/login?service=https%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        }

    def login(self):
        """登录。"""
        r = self.session.get(
            "https://passport.ustc.edu.cn/login?service=https%3A%2F%2Fweixine.ustc.edu.cn%2F2020%2Fcaslogin"
        )
        soup = bs(r.text, features="html.parser")
        cas_lt = soup.find(id="CAS_LT")["value"]
        # print('CAS_LT:', cas_lt)
        data = {
            "model": "uplogin.jsp",
            "CAS_LT": cas_lt,
            "service": "https://weixine.ustc.edu.cn/2020/caslogin",
            "warn": "",
            "showCode": "",
            "username": self.username,
            "password": self.password,
            "button": "",
        }
        r = self.session.post(
            "https://passport.ustc.edu.cn/login", data=data, allow_redirects=False
        )
        # print('Status code:', r.status_code)
        if r.status_code != 302:
            return False, f"错误的状态码：{r.status_code}"
        url = r.headers["Location"]
        r = self.session.get(url)
        if not "中国科大健康打卡平台" in r.text:
            return False, "重定向错误！"
        soup = bs(r.text, features="html.parser")
        self.soup = soup
        self.token = soup.find("input", attrs={"name": "_token"})["value"]
        # print('_token:', self.token)
        return True, "登录成功！"

    def checkin(self):
        """打卡。"""
        form = self.soup.find("form")
        data = {"_token": self.token}
        for item in form.find_all("input", {"class": "form-control"}):
            name = item["name"]
            value = item["value"]
            data[name] = value
        for item in form.find_all("textarea"):
            name = item["name"]
            value = item.string if item.string else ""
            data[name] = value
        for i in "has_fever", "last_touch_sars", "is_danger", "is_goto_danger":
            data[i] = form.find("input", {"name": i, "checked": True})["value"]
        data["body_condition"] = form.find("select", {"class": "form-control"}).find(
            "option", {"selected": True}
        )["value"]
        data["last_touch_sars_date"] = form.find(
            "input", {"name": "last_touch_sars_date"}
        )["value"]
        r = self.session.post(
            "https://weixine.ustc.edu.cn/2020/daliy_report", data=data
        )
        soup = bs(r.text, features="html.parser")
        msg = soup.find("p", class_="alert-success")
        if msg:
            msg = msg.text
        else:
            return False, '未能找到 "alert" 类，无法判断是否打卡成功！'
        if "上报成功" in msg:
            return True, "打卡成功！"
        else:
            return False, "未能找到提示信息，无法判断是否打卡成功！"

    def claim(self, dest: str, reason: str):
        """报备。"""
        r = self.session.get("https://weixine.ustc.edu.cn/2020/apply/daliy/i?t=3")
        t = time()
        data = [
            ("_token", self.token),
            ("start_date", strftime("%Y-%m-%d %H:%M:%S", localtime(t))),
            ("end_date", strftime("%Y-%m-%d 23:59:59", localtime(t))),
            ("reason", reason),
            ("t", t),
        ]
        for i in set(dest):
            if not i in "东西南北中":
                return False, '"dest" 参数错误！'
            data.append(("return_college[]", i + "校区"))
        r = self.session.post(
            "https://weixine.ustc.edu.cn/2020/apply/daliy/ipost",
            data=data,
            allow_redirects=True,
        )
        if not "报备成功" in r.text:
            return False, "未知原因报备失败！"
        return True, "报备成功！"

    def status(self):
        """当前状态。"""
        return self.soup.select_one("#daliy-report > form > div > p > strong").string

    def upload(
        self, image: bytes, t: int = 1, name: str = f"Screenshot_{int(time())}.jpg"
    ):
        """上传。
        | t | 含义 |
        | - | - |
        | 1 | 行程卡 |
        | 2 | 安康码 |
        | 3 | 核酸检测报告 |
        """
        # 图片压缩/调整大小
        img = Image.open(BytesIO(image))
        size = img.size
        img = img.resize((400, 400 * size[1] // size[0]))
        out = BytesIO()
        img.save(out, quality=80, optimize=True, format="JPEG")
        b = out.getvalue()
        html = self.session.get("https://weixine.ustc.edu.cn/2020/upload/xcm").text
        payload = {
            "_token": (None, self.token),
            "gid": (None, search(r"'gid': '(.*)'", html).groups()[0]),
            "sign": (None, search(r"'sign': '(.*)'", html).groups()[0]),
            "t": (None, str(t)),
            "id": (None, f"WU_FILE_{t - 1}"),
            "name": (None, name),
            "type": (None, "image/jpeg"),
            "lastModifiedDate": (
                None,
                strftime("%a %b %d %Y %H:%M:%S GMT+0800 (中国标准时间)"),
            ),
        }
        payload["file"] = (name, b, "image/jpeg")
        payload["size"] = (None, str(len(b)))
        encoder = MultipartEncoder(payload, boundary=gen_boundary())
        head = dict(self.session.headers)
        head["content-type"] = encoder.content_type
        r = self.session.post(
            "https://weixine.ustc.edu.cn/2020img/api/upload_for_student",
            data=encoder.to_string(),
            headers=head,
        )
        data = r.json()
        return data["status"], data["message"]

    def logout(self) -> bool:
        """登出。"""
        r = self.session.get("https://weixine.ustc.edu.cn/2020/rcaslogout")
        return "统一身份认证登出" in r.text

