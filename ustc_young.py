from requests import Session
from json import loads
import pandas as pd
from bs4 import BeautifulSoup
from random import choices
from string import ascii_letters, digits
from time import time


class Young:
    def __init__(self, username, password):
        self.logged_in = False
        self.modules = {
            "d": "德",
            "z": "智",
            "t": "体",
            "m": "美",
            "l": "劳",
        }
        self.username = username
        self.password = password
        self.session = Session()
        self.session.headers.update({
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
            "Referer": "https://passport.ustc.edu.cn/login?service=https%3A%2F%2Fyoung.ustc.edu.cn%2Flogin%2Fsc-wisdom-group-learning%2F",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        })
        session_id = "".join(choices(ascii_letters + digits, k=32)).upper()
        self.session.cookies.update({"JSESSIONID": session_id, "lang": "zh"})
        self.token = ''


    class Activity(object):
        def __init__(
            self,
            name: str,
            apply_end_time: str,
            module: str,
            hours: str,
            start_time: str,
            end_time: str,
            apply_people: str,
            total: str,
            type: str,
            series: str,
            status: str = None,
            series_name: str = None,
            registered: bool = False
        ):
            self.name = name
            self.apply_end_time = apply_end_time
            self.module = module
            self.hours = hours
            self.start_time = start_time
            self.end_time = end_time
            self.apply_people = apply_people
            self.total = total
            self.type = type
            self.series = series
            self.status = status
            self.series_name = series_name
            self.registered = registered

        def to_dict(self):
            return {
                "项目名称": self.name,
                "报名截止时间": self.apply_end_time,
                "模块": self.module,
                "学时": self.hours,
                "活动开始时间": self.start_time,
                "活动结束时间": self.end_time,
                "已申请人数": self.apply_people,
                "报名人数限制": self.total,
                "活动类型": self.type,
                "是否系列活动": self.series,
                "当前活动状态": self.status,
                "系列活动名称": self.series_name,
                "报名状态": self.registered
            }

    def login(self):
        login_url = "https://passport.ustc.edu.cn/login?service=https%3A%2F%2Fyoung.ustc.edu.cn%2Flogin%2Fsc-wisdom-group-learning%2F"
        r = self.session.get(login_url).text
        soup = BeautifulSoup(r, "html.parser")
        cas_lt = soup.find("input", {"name": "CAS_LT"})["value"]
        form_data = {
            "model": "uplogin.jsp",
            "CAS_LT": cas_lt,
            "service": "https://young.ustc.edu.cn/login",
            "warn": "",
            "showCode": "",
            "username": self.username,
            "password": self.password,
            "button": "",
        }
        r = self.session.post(login_url, data=form_data, allow_redirects=False)
        if r.status_code == 302:
            self.logged_in = True
        else:
            return False, "无法登录，请尝试检查用户名和密码！"
        url = r.headers["location"]
        ticket = url.split("ticket=")[1]
        get_token_url = f"https://young.ustc.edu.cn/login/wisdom-group-learning-bg/cas/client/checkSsoLogin?_t={int(time())}&ticket={ticket}&service=https:%2F%2Fyoung.ustc.edu.cn%2Flogin%2Fsc-wisdom-group-learning%2F"
        data = self.session.get(get_token_url).json()
        if data["code"] != 200:
            return False, "无法获取 X-Access-Token ！"
        token = data["result"]["token"]
        self.session.headers.update({"x-access-token": token,
        })
        return True, "登录成功！"

    def __del__(self):
        r = self.session.post(
            "https://young.ustc.edu.cn/login/wisdom-group-learning-bg/sys/logout", allow_redirects=False
        )
        assert r.status_code == 200, f"Failed to logout with status code {r.status_code}"

    def get_activity(self, hide_entered=True):
        cnt = 0
        page_num = 1
        total_num = 1
        res = []
        while cnt < total_num:
            url = f"https://young.ustc.edu.cn/login/wisdom-group-learning-bg/item/scItem/enrolmentList?_t=&column=createTime&order=desc&field=id,,action&pageNo={page_num}&pageSize=10"
            page_num = page_num + 1
            con = loads(self.session.get(url).text)["result"]
            total_num = int(con["total"])
            cnt += int(con["size"])
            records = con["records"]
            for item in records:
                if item["itemCategory_dictText"] == "系列项目":
                    id = item["id"]
                    children_url = (
                        "https://young.ustc.edu.cn/login/wisdom-group-learning-bg/item/scItem/selectSignChirdItem?_t=&id="
                        + id
                    )
                    children_con = self.session.get(children_url)
                    children_records = loads(children_con.text)["result"]

                    children_res = []
                    for children_item in children_records:
                        children_info = self.Activity(
                            name=children_item["itemName"],
                            apply_end_time=children_item["applyEt"],
                            module=self.modules[children_item["module"]],
                            hours=children_item["serviceHour"],
                            start_time=children_item["st"],
                            end_time=children_item["et"],
                            apply_people=children_item["applyNum"],
                            total=children_item["peopleNum"],
                            type=children_item["form_dictText"],
                            series="系列项目",
                            status=children_item["itemStatus_dictText"],
                            series_name=item["itemName"],
                            registered=item["booleanRegistration"]
                        )
                        children_res.append(children_info.to_dict())

                    children_df = pd.DataFrame(children_res)
                    enrolling = children_df.loc[children_df["当前活动状态"] == "报名中"]
                    if not enrolling.empty:
                        for value in enrolling.values:
                            item_info = self.Activity(
                                name=value[0],
                                apply_end_time=value[1],
                                module=value[2],
                                hours=value[3],
                                start_time=value[4],
                                end_time=value[5],
                                apply_people=value[6],
                                total=value[7],
                                type=value[8],
                                series="系列项目",
                                status=value[10],
                                series_name=value[11],
                                registered=value[12]
                            )
                            res.append(item_info.to_dict())
                else:
                    item_info = self.Activity(
                        name=item["itemName"],
                        apply_end_time=item["applyEt"],
                        module=self.modules[item["module"]],
                        hours=item["serviceHour"],
                        start_time=item["st"],
                        end_time=item["et"],
                        apply_people=item["applyNum"],
                        total=item["peopleNum"],
                        type=item["form_dictText"],
                        series="单次项目",
                        registered=item["booleanRegistration"]
                    )
                    res.append(item_info.to_dict())

        df = pd.DataFrame(res)
        module_df = df.groupby("模块")

        ret = ""
        for key, value in module_df:
            flag = True
            for item in value.values:
                if hide_entered and item[12]:
                    continue
                if flag:
                    ret += f"{item[2]}:\n"
                    flag = False
                ret += f'  {item[0]} {item[8]} 学时 {item[3]}\n    申请人数: {item[6]}/{item[7]}\n    报名截止: {item[1]}\n    活动开始: {item[4]}\n    活动结束: {item[5]}\n'
                if item[9] == "系列项目":
                    ret += f"    系列活动名: {item[11]}\n"
        return ret.strip()


if __name__ == "__main__":
    username = ""
    password = ""
    young = Young(username, password)
    young.login()
    print(young.get_activity())
    del young

