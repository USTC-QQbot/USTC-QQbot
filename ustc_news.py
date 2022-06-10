from re import findall
from requests import get
from bs4 import BeautifulSoup
from feedparser import parse
from time import strftime


def request_news(src):
    """返回当天和前一天的新闻,如没有符合条件则返回最新的一条
    xwbl - 新闻博览
    mtgz - 媒体关注
    """
    con = get(f"https://news.ustc.edu.cn/{src}.htm")
    con.encoding = con.apparent_encoding
    con = con.text
    soup = BeautifulSoup(con, "html.parser").find(
        name="ul", attrs={"class": "clearfix info-list"}
    )
    lead = {"xwbl": "新闻博览", "mtgz": "媒体关注"}

    res = f"这是最近的{lead[src]}:"
    i = 0
    for child in soup.children:
        date = BeautifulSoup(str(child), "html.parser").find(
            name="div", attrs={"class": "date col-sm-3 col-xs-12 text-right"}
        )
        if date == None:
            continue
        i = i + 1
        if i < 11:
            title = (
                findall(r'title="([^"]+)"', str(child))[0]
                .replace("&lt;", "<")
                .replace("&gt;", ">")
            )
            href = findall(r'href="([^"]+)"', str(child))[0]
            res = f"{res}\n{str(i)}.{date.text} {str(title)} https://news.ustc.edu.cn/{str(href)}"
    return res


def get_newspaper(num=0):
    """no为期数,默认获取最新一期中国科大报"""
    con = get("https://zgkdb.ustc.edu.cn/")
    con.encoding = con.apparent_encoding
    con = con.text
    titles = findall(r"d_title= \[(.+)\]", con)[0].replace("'", "").split(",")
    for i in range(len(titles)):
        if "-" in titles[i]:
            titles[i] = titles[i][: titles[i].index("-")]
    choices = findall(r"d_url= \[(.+)\]", con)[0].replace("'", "").split(",")
    if num:
        if not (str(num) in titles):
            return f"无效数字,请从{titles[-1]}-{titles[0]}中选取一个数字(部分数字无对应期报纸)"
        else:
            num = choices[titles.index(str(num))]
    else:
        num = int(choices[0])
    cur_url = "https://zgkdb.ustc.edu.cn/?qcid=" + str(num)
    con = get(cur_url)
    con.encoding = con.apparent_encoding
    con = con.text
    pages = findall(r'onclick="change_page\([^,]+,([^)]+)\)"', con)
    soup = BeautifulSoup(con, "html.parser").find("strong")
    res = f"中国科大报第{soup.text}期 {cur_url}"
    for page in pages:
        cur_url = f"https://zgkdb.ustc.edu.cn/?qcid={str(num)}&bcid={page}"
        con = get(cur_url)
        con.encoding = con.apparent_encoding
        con = con.text
        soup = BeautifulSoup(con, "html.parser").find_all("li")
        if not soup:
            break
        else:
            for li in soup:
                spe = findall(r'onclick="show_art\([^,]+,[^,]+,\'(\d+)\'\)', str(li))[0]
                res = f"{res}\n{li.text} {cur_url}&nid={spe}"
    res = res + "\nPDF下载:"
    for page in pages:
        res = f"{res}\nhttps://zgkdb.ustc.edu.cn/?a=d&i={page}"
    return res


def request_rss(type_: int, n=0, max_=10):
    """`type_`: 0: "news", 1: "notice"."""
    if n < 0 or n > max_:
        return f"请输入一个 1~{max_} 的整数！"
    urls = (
        "https://www.ustc.edu.cn/system/resource/code/rss/rssfeedg.jsp?type=list&treeid=1175&viewid=249541&mode=10&dbname=vsb&owner=1585251974&ownername=zz&contentid=236926&number=",
        "https://www.ustc.edu.cn/system/resource/code/rss/rssfeedg.jsp?type=list&treeid=1002&viewid=249541&mode=10&dbname=vsb&owner=1585251974&ownername=zz&contentid=221571&number=",
    )
    lead = ("科大要闻", "通知公告")[type_]
    r = get(urls[type_] + str(n if n else max_))
    r.encoding = r.apparent_encoding
    contents = parse(r.text)["entries"]
    if not n:
        res = f"这是最近的{lead}:\n"
        for i, item in enumerate(contents):
            res += f"{i + 1}. [{strftime('%Y-%m-%d', item['updated_parsed'])}] {item['title']}\n"
    else:
        res = f"第 {n} 条{lead}如下:\n"
        item = contents[n - 1]
        res += f"[{strftime('%Y-%m-%d', item['updated_parsed'])}] {item['title']}\n{item['summary']}\n链接: {item['link']}\n"
    return res.strip()

if __name__ == "__main__":
    # print(request_news("xwbl"))  # 新闻博览
    # print(request_news("mtgz"))  # 媒体关注
    # print(get_newspaper())  # 获取中国科大报内容
    print(request_rss(1, 5))
    print(request_rss(0))
