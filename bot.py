from inspect import currentframe, getframeinfo
from json import dump, dumps, load
from os import listdir, remove
from os.path import isfile
from shutil import copyfile
from random import choice, sample, randrange
from re import search
from time import strftime, time
from urllib.parse import quote

import matplotlib.pyplot as plt
from aiocqhttp import CQHttp, Event, Message, MessageSegment, exceptions
from matplotlib import rcParams
from qrcode import make
from requests import get
from socket import timeout
from mcstatus import JavaServer
from pangu import spacing_text

from make_quotation import make_quotation
from stretch_image import make_stretch_image
# from meme_recog import is_Capoo
from ustc_auth import valid
from ustc_news import request_rss
from ustc_young import Young


def msg_to_txt(msg: Message) -> str:
    res = ""
    for seg in msg:
        if seg["type"] == "text":
            res += seg["data"]["text"]
    return res.strip()


def msg_split(msg: Message):
    cmd = ""
    empty = []
    for i, seg in enumerate(msg):
        if seg["type"] == "text":
            cmd: str = seg["data"]["text"].strip()
            if cmd:
                cmd = cmd.partition(" ")
                if cmd[2]:
                    seg["data"]["text"] = cmd[2].lstrip()
                else:
                    empty.append(i)
                cmd = cmd[0]
                break
    for i in range(len(empty)):
        del msg[empty.pop()]
    return cmd, msg


def get_mentioned(msg: Message) -> set:
    mentioned = set()
    for seg in msg:
        if seg["type"] == "at":
            mentioned.add(seg["data"]["qq"])
    return set(map(int, mentioned))


def get_pic(msg: Message) -> str:
    for seg in msg:
        if seg["type"] == "image":
            return seg["data"]["url"]
    return ''


def load_config():
    global full_config, mental_templates
    full_config = {}
    with open("./config_base.json") as f:
        full_config["base"] = load(f)
    group_configs = filter(
        lambda path: path.endswith(".json"), listdir("./group_config")
    )
    for group_config in group_configs:
        with open("./group_config/" + group_config) as f:
            full_config[int(group_config[:-5])] = load(f)
    with open("./config_override.json") as f:
        full_config["override"] = load(f)
    with open("./data/mental.txt", encoding="utf-8") as f:
        mental_templates = f.readlines()


def get_config(func_name: str = "", group_id: int = 0) -> dict:
    caller = currentframe().f_back
    if not func_name:
        func_name = getframeinfo(caller)[2]
    if not group_id:
        event = caller.f_locals.get("event")
        if not event:
            return {}
        if event.detail_type == "group":
            group_id = event.group_id
            attrs = [
                "base",
                group_id,
                "override",
            ]
        else:
            attrs = ["base", "override"]
    config = {}
    for attr in attrs:
        config.update(full_config.get(attr, {}).get(func_name, {}))
    return config


def set_config(option: str, value, func_name: str = "", group_id: int = 0):
    """Set group config."""
    caller = currentframe().f_back
    if not func_name:
        func_name = getframeinfo(caller)[2]
    if not group_id:
        event = caller.f_locals.get("event")
        if not event:
            return
        if event.detail_type == "group":
            group_id = event.group_id
        else:
            return
    if group_id >= 0:
        path = f"./group_config/{group_id}.json"
    else:
        return
    group_config = dict(full_config.get(group_id, {}))
    base_config = dict(full_config.get("base", {}))
    func_config = dict(base_config.get(func_name, {}))
    func_config.update(group_config.get(func_name, {}))
    func_config[option] = value
    group_config[func_name] = func_config
    full_config[group_id] = group_config
    with open(path, "w", encoding="utf-8") as f:
        dump(group_config, f, indent=4)


def unset_config(func_name: str = "", option=None, group_id: int = 0) -> str:
    """Unset the config."""
    caller = currentframe().f_back
    if not func_name:
        func_name = getframeinfo(caller)[2]
    if not group_id:
        event = caller.f_locals.get("event")
        if not event:
            return "内部错误 - 未找到 event ！"
        if event.detail_type == "group":
            group_id = event.group_id
        else:
            return "只能在群聊使用！"
    if group_id >= 0:
        path = f"./group_config/{group_id}.json"
    else:
        return "内部错误 - group_id 非法！"
    group_config = dict(full_config.get(group_id, {}))
    base_config = dict(full_config.get("base", {}))
    func_config = dict(base_config.get(func_name, {}))
    if not func_name in group_config:
        return "此函数不存在或没有配置。"
    if option != None:
        func_config.update(group_config.get(func_name, {}))
        if option in base_config.get(func_name, {}):
            func_config[option] = base_config[func_name][option]
        else:
            return "非法的 option ！"
        group_config[func_name] = func_config
    else:
        del group_config[func_name]
    full_config[group_id] = group_config
    with open(path, "w", encoding="utf-8") as f:
        dump(group_config, f, indent=4)
    return "重置成功！"


def get_cred(qq: int):
    path = f"./credential/{qq}.json"
    if not isfile(path):
        cred = {}
    else:
        with open(path, encoding="utf-8") as f:
            cred: dict = load(f)
    return cred


async def can_ban(event: Event, refresh=False) -> bool:
    """是否能够禁言发送者"""
    group_id = event.group_id
    sender = event.sender["user_id"]
    if sender == 80000000:
        return False
    self = await bot.get_group_member_info(group_id=group_id, user_id=event.self_id, no_cache=refresh)
    sender = await bot.get_group_member_info(group_id=group_id, user_id=sender, no_cache=refresh)
    if sender["role"] == "owner" or self["role"] == "member":
        return False
    elif self["role"] == "owner":
        return True
    else:
        return sender["role"] == "member"


async def roll(event, msg: Message):
    """生成随机数。

    /roll - 生成配置文件中指定范围 (默认 1 ~ 6) 的随机数。
    /roll <start> <end> - 生成 [<start>, <end>] 的随机数。
    /roll *args - 在 args 里随机选择一个。
    """
    cmds = msg_to_txt(msg).split()
    if len(cmds) == 0:
        config = get_config()
        await bot.send(event, f"你摇到了 {randrange(config['start'], config['end'] + 1)} ！")
        return
    elif len(cmds) == 2:
        try:
            start, end = int(cmds[0]), (int(cmds[1]) + 1)
            result = randrange(start, end)
        except:
            result = choice()
    else:
        result = choice(cmds)
    await bot.send(event, f"你摇到了 {result} ！")


async def echo(event, msg: Message):
    """重复你说的话。"""
    if len(msg):
        await bot.send(event, msg)


async def ban(event: Event, msg: Message):
    """禁言指定用户。

    /ban *@someone <duration> - 禁言提及的人员 <duration>s 。
    a. 可指定多位成员，@全体成员则全体禁言。
    b. <duration> 未指定则为 60 ，指定为 0 则取消禁言。
    <reply> /ban <duration> - 禁言被回复消息的发送者，暂未支持匿名。
    """
    qqs = set()
    duration = 60
    for seg in msg:
        if seg["type"] == "at":
            qqs.add(int(seg["data"]["qq"]))
        elif seg["type"] == "text":
            try:
                duration = int(seg["data"]["text"].strip())
            except:
                pass
        elif seg["type"] == "reply":
            id_ = int(seg["data"]["id"])
            replied = await bot.get_msg(message_id=id_)
            qq = replied["sender"]["user_id"]
            if qq != 80000000:
                qqs.add(qq)
    role = await bot.get_group_member_info(
        group_id=event.group_id, user_id=event.self_id
    )
    role = role["role"]
    if role == "member":
        return
    if "all" in qqs:
        await bot.set_group_whole_ban(group_id=event.group_id, enable=bool(duration))
        return
    for qq in qqs:
        try:
            await bot.set_group_ban(
                group_id=event.group_id, user_id=qq, duration=duration
            )
        except exceptions.ActionFailed:
            pass


async def query(event: Event, msg: Message):
    """站内搜索: /query <keyword> 。"""
    config = get_config()
    cmd = msg_to_txt(msg)
    cmds = cmd.split()
    if len(cmds) == 0:
        await bot.send(event, config["insufficient"])
        return
    teacher = cmds[0]
    url = config["engine"].format(quote(teacher))
    await bot.send(event, config["format"].format(teacher, url))


async def latex(event: Event, msg: Message):
    """渲染 Latex 公式: /latex <formula> 。"""
    formula = msg_to_txt(msg).strip()
    if not formula:
        return
    formula_ = f"${formula}$"
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, formula_, fontsize=18)
    fname = f"latex_{time()}.png"
    path = CQ_PATH + "/data/images/" + fname
    try:
        fig.savefig(
            path,
            dpi=750,
            transparent=False,
            format=fname.split(".")[-1],
            bbox_inches="tight",
            pad_inches=0.05,
        )
    except RuntimeError:
        config = get_config()
        await bot.send(event, config["fail"])
        return
    await bot.send(event, Message(MessageSegment.image(fname)))
    remove(path)


async def show_time(event: Event, msg: Message):
    """发送当前时间及时间戳。"""
    timestamp = int(time())
    time_ = strftime("%Y-%m-%d %H:%M:%S")
    await bot.send(event, f"当前时间：{time_}\n时间戳：{timestamp}")


async def enable(event: Event, msg: Message):
    """启用机器人。"""
    global enabled
    enabled = True
    await bot.send(event, "机器人已启用。")


async def disable(event: Event, msg: Message):
    """禁用机器人。"""
    global enabled
    enabled = False
    await bot.send(event, "机器人已禁用。")


async def smart_question(event: Event, msg: Message):
    """发送《提问的智慧》链接。"""
    await bot.send(
        event,
        "《提问的智慧》\n  [简中]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/\n  [繁/简]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way\n  [英语]原文: http://www.catb.org/~esr/faqs/smart-questions.html\n  [简中]思维导图：https://ld246.com/article/1536732337028",
    )


async def wtf(event: Event, msg: Message):
    """RTFM/STFW 是什么意思？"""
    await bot.send(
        event,
        "RTFM/STFW 是什么意思？\n  [简中]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/#%E5%A6%82%E4%BD%95%E8%A7%A3%E8%AF%BB%E7%AD%94%E6%A1%88\n  [繁/简]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way#rtfm%E5%92%8Cstfw%E5%A6%82%E4%BD%95%E7%9F%A5%E9%81%93%E4%BD%A0%E5%B7%B2%E5%AE%8C%E5%85%A8%E6%90%9E%E7%A0%B8%E4%BA%86\n  [英语]原文: http://www.catb.org/~esr/faqs/smart-questions.html#rtfm",
    )


async def just_ask(event: Event, msg: Message):
    """不要问有没有人，请直接问。"""
    await bot.send(event, "不要问有没有人，请直接问\n  中译：https://fars.ee/~justask.html\n  原文：https://sol.gfxile.net/dontask.html")


async def isbn(event: Event, msg: Message):
    """根据提供的 ISBN 号查询书籍信息。"""
    serial = msg_to_txt(msg).partition(" ")[0]
    if not serial:
        await bot.send(event, "未提供 ISBN ！")
        return
    config = get_config()
    key = config.get("apikey")
    if not key:
        await bot.send(event, "未配置 apikey ！·")
        return
    r = get(f"https://api.jike.xyz/situ/book/isbn/{serial}", params={"apikey": key})
    if "isbn 错误!" in r.text:
        await bot.send(event, "ISBN 错误！")
        return
    data = r.json()
    if data["msg"] == "请求成功":
        data = data["data"]
        msg_ = f'{data["name"]}\n作者：{data["author"]}\n出版社：{data["publishing"]}\n出版时间：{data["published"]}\n页数：{data["pages"]}\n价格：{data["price"]}\n简介：{data["description"]}'
        await bot.send(event, msg_)
    else:
        await bot.send(event, data["msg"])


async def qrcode(event: Event, msg: Message):
    """制作二维码。"""
    data = msg_to_txt(msg)
    try:
        qr = make(data)
    except:
        await bot.send(event, "文本过大！")
        return
    fname = f"qrcode_{time()}.png"
    path = CQ_PATH + "/data/images/" + fname
    qr.save(path)
    qr.close()
    await bot.send(event, Message(MessageSegment.image(fname)))
    remove(path)


async def news(event: Event, msg: Message):
    """获取科大要闻。

    /news - 获取 10 条科大要闻。
    /news <i> - 查看第 <i> 条的摘要与链接。
    """
    arg = msg_to_txt(msg).strip()
    if not arg:
        await bot.send(event, request_rss(0))
    elif arg.isdigit():
        await bot.send(event, request_rss(0, int(arg)))
    else:
        await bot.send(event, "请传入合法参数！")


async def young(event: Event, msg: Message):
    """获取二课活动。

    /young - 获取未参加可报名的二课。
    /young all - 获取所有可报名的二课。
    * 需要通过私聊命令 /cred 配置私人凭据中 username 和 password 为学号和密码。
    e.g. /cred username PBxxxxxxx, /cred password xxxxxx
    """
    cmds = msg_to_txt(msg).split()
    show_all = False
    if len(cmds) == 1 and cmds[0] == "all":
        show_all = True
    elif len(cmds) != 0:
        await bot.send(event, "参数错误！")
        return
    sender = event.sender.get("user_id", 0)
    if not sender:
        return
    cred = get_cred(sender)
    username = cred.get("username", None)
    password = cred.get("password", None)
    if username == None or password == None:
        await bot.send(event, "凭据不足！")
        return
    clint = Young(username, password)
    res = clint.login()
    if not res[0]:
        await bot.send(event, res[1])
        return
    r = clint.get_activity(hide_entered=not show_all)
    await bot.send(event, r)


async def notice(event: Event, msg: Message):
    """获取通知公告。

    /notice - 获取 10 条通知公告。
    /notice <i> - 查看第 <i> 条的摘要与链接。
    """
    arg = msg_to_txt(msg).strip()
    if not arg:
        await bot.send(event, request_rss(1))
    elif arg.isdigit():
        await bot.send(event, request_rss(1, int(arg)))
    else:
        await bot.send(event, "请传入合法参数！")


async def turntable(event: Event, msg: Message):
    """俄罗斯轮盘赌。"""
    config = get_config()
    sender = event.sender["user_id"]
    if not await can_ban(event):
        await bot.send(event, "你是不是玩不起？")
        return
    info = await bot.get_group_member_info(group_id=event.group_id, user_id=sender)
    nickname = info["card"] if info["card"] else info["nickname"]
    left = config["left"]
    load = True
    shot = False
    for i in range(len(left)):
        left[i] -= 1
        load = load and (left[i] <= 0)
        shot = shot or (left[i] == 0)
    if shot:
        duration = randrange(config["min"], config["max"] + 1)
        await bot.set_group_ban(
            group_id=event.group_id, user_id=sender, duration=duration
        )
        await bot.send(event, "砰！一声枪响之后，{0}被禁言了{1}s！".format(nickname, duration))
    else:
        await bot.send(event, "{}无事发生".format(nickname))
    if load:
        capacity = config["capacity"]
        bullets = config["bullets"]
        assert capacity >= bullets
        left = sample(range(1, capacity + 1), bullets)
        left.sort()
        await bot.send(event, "子弹射尽，已重新上膛。")
    set_config("left", left)


async def meme(event: Event, msg: Message):
    """判断回复的图片是不是猫猫虫。"""
    await bot.send(event, "由于性能原因，此功能被禁用！")
    return
    if len(msg):
        reply_seg = msg[0]
    else:
        await bot.send(event, "您未回复图片！")
        return
    if reply_seg["type"] == "reply":
        try:
            replied = (await bot.get_msg(message_id=int(reply_seg["data"]["id"])))[
                "message"
            ]
        except Exception as e:
            print(e)  # DEBUG
            await bot.send(event, "未能定位消息，请尝试使用手机QQ操作！")
            return
        url = get_pic(replied)
        if not url:
            await bot.send(event, "您未回复图片！")
            return
    else:
        await bot.send(event, "您未回复图片！")
        return
    result = is_Capoo(url, True)
    if result == 0:
        await bot.send(event, "是猫猫虫！")
        await bot.send(event, Message(MessageSegment.image("yes.gif")))
    elif result == 1:
        await bot.send(event, "不是猫猫虫...")
        await bot.send(event, Message(MessageSegment.image("no.gif")))
    else:
        await bot.send(event, "未知错误！")
        await bot.send(event, Message(MessageSegment.image("error.gif")))


async def get_url(event: Event, msg: Message):
    """获取回复的图片直链。"""
    if len(msg):
        reply_seg = msg[0]
    else:
        await bot.send(event, "您未回复图片！")
        return
    if reply_seg["type"] == "reply":
        try:
            replied = (await bot.get_msg(message_id=int(reply_seg["data"]["id"])))[
                "message"
            ]
        except:
            await bot.send(event, "未能定位消息，请尝试使用手机QQ操作！")
            return
        url = get_pic(replied)
        if not url:
            await bot.send(event, "您未回复图片！")
            return
        await bot.send(event, url)
    else:
        await bot.send(event, "您未回复图片！")


async def parrot(event: Event, msg: Message):
    """🦜

    /parrot - 随机发送一张 gif
    /parrot <name> - 发送指定的 gif
    """
    cmd = msg_to_txt(msg)
    fname = f"parrot_{time()}.png"
    path = CQ_PATH + "/data/images/" + fname
    all_parrots = listdir("./data/parrots/")
    if not cmd:
        chosen = choice(all_parrots)
    elif cmd in all_parrots:
        chosen = cmd
    elif cmd + ".gif" in all_parrots:
        chosen = cmd + ".gif"
    else:
        await bot.send(event, "🦜 not found!")
        return
    copyfile("./data/parrots/" + chosen, path)
    msg_ = Message(chosen[:-4])
    msg_.append(MessageSegment.image(fname))
    try:
        await bot.send(event, msg_)
    except exceptions.ActionFailed:
        await bot.send(event, chosen[:-4] + "发送失败！")
    remove(path)


async def ikun(event: Event, msg: Message):
    """🐔

    /ikun - 随机发送一张坤坤
    """
    fname = f"ikun_{time()}.png"
    path = CQ_PATH + "/data/images/" + fname
    all_ikuns = listdir("./data/ikun/")
    chosen = choice(all_ikuns)
    copyfile("./data/ikun/" + chosen, path)
    msg_ = Message()
    msg_.append(MessageSegment.image(fname))
    try:
        await bot.send(event, msg_)
    except exceptions.ActionFailed:
        await bot.send(event, chosen + "发送失败！")
    remove(path)


async def quotation(event: Event, msg: Message):
    """制作语录。"""
    if len(msg):
        reply_seg = msg[0]
    else:
        await bot.send(event, "您未回复消息！")
        return
    if reply_seg["type"] == "reply":
        try:
            ret = await bot.get_msg(message_id=int(reply_seg["data"]["id"]))
            replied = ret["message"]
        except Exception as e:
            print(e)  # DEBUG
            await bot.send(event, "未能定位消息，请尝试使用手机QQ操作！")
            return
    else:
        await bot.send(event, "您未回复消息！")
        return
    saying = msg_to_txt(replied)
    if not saying:
        url = get_pic(replied)
        if not url:
            await bot.send(event, "你回复了个啥？")
            return
        r = get(url)
        saying = r.content
    sender = ret["sender"]["user_id"]
    if sender == 80000000:
        await bot.send(event, "暂不支持匿名消息。")
        return
    avatar = get(f"http://q2.qlogo.cn/headimg_dl?dst_uin={sender}&spec=100").content
    info = await bot.get_group_member_info(group_id=event.group_id, user_id=sender)
    name = info["card"] if info["card"] else info["nickname"]
    try:
        img = make_quotation(avatar, saying, name)
    except ValueError as e:
        await bot.send(event, ", ".join(e.args))
        return
    fname = f"quotation_{time()}.jpg"
    path = CQ_PATH + "/data/images/" + fname
    img.save(path)
    img.close()
    await bot.send(event, Message(MessageSegment.image(fname)))
    remove(path)


async def stretch(event: Event, msg: Message):
    """制作拉伸图：/stretch <text>"""
    text = msg_to_txt(msg)
    if not text:
        await bot.send(event, "你要生成啥？")
        return
    elif len(text) > 50:
        await bot.send(event, "字数太多辣！")
        return
    img = make_stretch_image(text)
    fname = f"stretch_{time()}.jpg"
    path = CQ_PATH + "/data/images/" + fname
    img.save(path)
    img.close()
    await bot.send(event, Message(MessageSegment.image(fname)))
    remove(path)


async def mental(event: Event, msg: Message):
    """发癫。

    /犯病(💈) - 对发送者发癫。
    /犯病(💈) txt/at - 对指定对象发癫。"""
    arg = msg_to_txt(msg).strip()
    mentioned = get_mentioned(msg)
    qq = 0
    if mentioned:
        qq = mentioned.pop()
    elif arg:
        name = arg
    else:
        qq = event.sender["user_id"]
    if qq:
        if qq != 80000000:
            info = await bot.get_group_member_info(group_id=event.group_id, user_id=qq)
            name = info["card"] if info["card"] else info["nickname"]
        else:
            name = event.anonymous["name"]
    template = choice(mental_templates)
    await bot.send(event, template.format(name).strip())


async def uf(event: Event, msg: Message):
    """获取一条没有用的冷知识。
    
    /uf - 随机获取一条
    /uf <id> - 获取指定 id 的冷知识
    """
    id_ = msg_to_txt(msg).strip()
    if id_:
        r = get('https://uselessfacts.jsph.pl/api/v2/facts/' + id_)
    else:
        r = get('https://uselessfacts.jsph.pl/api/v2/facts/random')
    if not r.text.startswith('{'):
        await bot.send(event, "获取失败：" + r.text)
        return
    r = r.json()
    id_ = r['id']
    source = r['source_url']
    content = r['text']
    await bot.send(event, f"{content}\n\nFrom: {source}\nID: {id_}")


async def mc(event: Event, msg: Message):
    """查询指定的 MC Java 服务器状态。"""
    ip_addr = msg_to_txt(msg)
    # 未指定 ip 地址，从配置文件查找默认 ip
    if not ip_addr:
        config = get_config()
        if not config["ip"]:
            await bot.send(event, "未指定服务器地址!")
            return
        else:
            ip_addr = config["ip"]
    # ip 地址合法性校验
    try:
        server = JavaServer.lookup(ip_addr)
    except ValueError:
        await bot.send(event, f"给定的服务器地址 \"{ip_addr}\" 不合法! 正确的服务器地址格式: example.com:25565")
        return
    except Exception as e:
        await bot.send(event, f"未知错误: {e}!")
        return
    # 状态查询
    try:
        status = server.status()
    except timeout:
        await bot.send(event, f"服务器 \"{ip_addr}\" 超时!")
        return
    # 生成回复
    response = f"服务器: \"{ip_addr}\"\n描述: {status.description}\n版本: {status.version.name}\t延迟: {round(status.latency, 2)}ms\t在线: {status.players.online}/{status.players.max}"
    if status.players.sample:
        response += "\n在线玩家: "
        for player in status.players.sample:
            response += player.name + ", "
        response = response[:-2]
    await bot.send(event, response)


async def pangu(event: Event, msg: Message):
    """如果你跟我一樣，每次看到網頁上的中文字和英文、數字、符號擠在一塊，就會坐立難安，忍不住想在它們之間加個空格。這個外掛（支援 Chrome 和 Firefox）正是你在網路世界走跳所需要的東西，它會自動替你在網頁中所有的中文字和半形的英文、數字、符號之間插入空白。

    漢學家稱這個空白字元為「盤古之白」，因為它劈開了全形字和半形字之間的混沌。另有研究顯示，打字的時候不喜歡在中文和英文之間加空格的人，感情路都走得很辛苦，有七成的比例會在 34 歲的時候跟自己不愛的人結婚，而其餘三成的人最後只能把遺產留給自己的貓。畢竟愛情跟書寫都需要適時地留白。
    與大家共勉之。

    https://github.com/vinta/pangu.py"""
    text = msg_to_txt(msg)
    text = spacing_text(text)
    await bot.send(event, text)


async def help(event: Event, msg: Message):
    """显示帮助信息。

    /help - 列出可用指令。
    /help <func> - 展示 <func> 的帮助信息。
    """
    command = "/" + msg_to_txt(msg).strip().removeprefix("/")
    admins = get_config("admin").get("list", [])
    is_su = event.sender.get("user_id", 0) == SUPER_USER
    is_admin = is_su or (event.sender.get("user_id", 0) in admins)
    if event.detail_type == "group":
        commands = dict(group_commands)
        if is_admin:
            commands.update(admin_group_commands)
        if is_su:
            commands.update(su_group_commands)
        else:
            disabled = set()
            for index, command_ in commands.items():
                if not get_config(command_.__name__).get("enabled", True):
                    disabled.add(index)
            for index in disabled:
                commands.pop(index)
    elif event.detail_type == "private":
        commands = dict(private_commands)
        if is_su:
            commands.update(su_private_commands)
    if command == "/":
        await bot.send(event, "可用指令: " + ", ".join(commands))
    elif command in commands:
        func = commands[command]
        await bot.send(
            event,
            func.__doc__.strip() if func.__doc__ else "此指令没有帮助信息。",
        )
    else:
        await bot.send(event, f'没有名为 "{command}" 的指令。')


async def admin(event: Event, msg: Message):
    """控制群聊的机器人管理员。

    /admin (list) - 列出所有机器人管理员。
    /admin add *@someone - 把提及的人设为机器人管理员。
    /admin rm/del/remove *@someone - 把提及的人移出机器人管理员。
    /admin clear - 移除所有机器人管理员。
    """
    cmds = msg_to_txt(msg).split()
    admins: list = get_config().get("list", [])
    mentioned = get_mentioned(msg)
    if not cmds:
        await bot.send(
            event, "群聊的机器人管理员: " + (", ".join(map(str, admins)) if admins else "None")
        )
        return
    elif len(cmds) == 1:
        cmd = cmds[0]
        reply = "?"
        if cmd == "clear":
            admins = []
            reply = "已移除所有机器人管理员。"
        elif cmd == "list":
            reply = "群聊的机器人管理员: " + (", ".join(map(str, admins)) if admins else "None")
        elif cmd == "add":
            reply = "将以下人员设为机器人管理员: "
            flag = False
            for candidate in mentioned:
                if candidate not in admins:
                    flag = True
                    admins.append(candidate)
                    reply += f"{candidate}, "
            if not flag:
                reply = "未添加任何人为机器人管理员。"
            else:
                reply = reply[:-2]
        elif cmd in ("rm", "del", "remove"):
            reply = "将以下人员移出机器人管理员: "
            flag = False
            for candidate in mentioned:
                if candidate in admins:
                    flag = True
                    admins.remove(candidate)
                    reply += f"{candidate}, "
            if not flag:
                reply = "未将任何人移出机器人管理员。"
            else:
                reply = reply[:-2]
        set_config("list", admins)
        await bot.send(event, reply)
    else:
        await bot.send(event, "过多参数！")


async def config_group(event: Event, msg: Message):
    """修改机器人的群聊配置。

    /config <func> - 展示 <func> 的当前配置。
    /config <func> <option> - 展示 <option> 的当前值。
    /config <func> <option> <value> - 把 <option> 的值设为 <value> 。
    /config unset <func> - 重置 <func> 的群组配置。
    /config unset <func> <option> - 重置 <option> 的值。
    /config reload - 重新加载配置。
    """
    cmds = msg_to_txt(msg).split()
    if not cmds:
        return
    if cmds[0] == "unset":
        if len(cmds) == 1:
            await bot.send(event, "参数不足！")
            return
        elif len(cmds) == 2:
            ret = unset_config(cmds[1])
        elif len(cmds) == 3:
            ret = unset_config(cmds[1], cmds[2])
        else:
            await bot.send(event, "参数过多！")
            return
        await bot.send(event, ret)
        return
    elif cmds[0] == "reload":
        load_config()
        await bot.send(event, "已重新加载配置。")
        return
    func = group_commands.get(cmds[0], None)
    if func:
        config = get_config(func.__name__)
    else:
        config = get_config(cmds[0])
    if not config:
        await bot.send(event, "未找到指定函数。")
        return
    if len(cmds) == 1:
        await bot.send(event, dumps(config, ensure_ascii=False, indent=4))
    elif len(cmds) == 2:
        await bot.send(event, str(config.get(cmds[1])))
    elif len(cmds) == 3:
        option, value = cmds[1:]
        try:
            value = eval(value)
        except:
            pass
        set_config(option, value, func_name=cmds[0])
        await bot.send(event, "操作成功。")


async def credential(event: Event, msg: Message):
    """查看/修改个人凭据信息。

    /cred - 查看所有保存的凭据信息。
    /cred <name> - 查看凭据内 <name> 项的值。
    /cred <name> <value> - 新建/修改 <name> 的值为 <value> 。
    /cred del <name> - 删除 <name> 的值。
    /cred del - 删除所有凭据。
    """
    sender = event.sender.get("user_id", 0)
    if not sender:
        return
    path = f"./credential/{sender}.json"
    cred = get_cred(sender)
    cmds = msg_to_txt(msg).split()
    if not cmds:
        await bot.send(event, dumps(cred, indent=4, ensure_ascii=False))
        return
    if len(cmds) == 1:
        if cmds[0] == "del":
            remove(path)
            await bot.send(event, "操作成功。")
            return
        else:
            await bot.send(
                event, "此项不存在。" if not cmds[0] in cred else str(cred[cmds[0]])
            )
            return
    elif len(cmds) == 2:
        if cmds[0] == "del":
            if cmds[1] in cred:
                del cred[cmds[1]]
            else:
                await bot.send(event, "此项不存在。")
                return
        else:
            cred[cmds[0]] = int(cmds[1]) if cmds[1].isdigit() else cmds[1]
    with open(path, "w", encoding="utf-8") as f:
        dump(cred, f, indent=4, ensure_ascii=False)
    await bot.send(event, "操作成功。")


full_config = {}
load_config()
PORT: int = full_config["override"].get("PORT")
SUPER_USER: int = full_config["override"].get("SUPER-USER")
CQ_PATH: str = full_config["override"].get("CQ-PATH")
bot = CQHttp()
enabled = True
rcParams["text.usetex"] = True
rcParams["text.latex.preamble"] = "\\usepackage{amsmath}\n\\usepackage{mathabx}"

private_commands = {
    "/roll": roll,
    "/time": show_time,
    "/query": query,
    "/help": help,
    "/latex": latex,
    "/news": news,
    "/notice": notice,
    "/cred": credential,
    "/young": young,
    "/echo": echo,
    "/isbn": isbn,
    "/qr": qrcode,
    # "/meme": meme,
    "/stretch": stretch,
    "/parrot": parrot,
    "/url": get_url,
    "/ikun": ikun,
    "/mc": mc,
    "/uf": uf,
    "/pangu": pangu
}
group_commands = {
    "/roll": roll,
    "/time": show_time,
    "/提问的智慧": smart_question,
    "/rtfm": wtf,
    "/stfw": wtf,
    "/justask": just_ask,
    "/直接问": just_ask,
    "/query": query,
    "/help": help,
    "/latex": latex,
    "/news": news,
    "/notice": notice,
    "/毛子转盘": turntable,
    "/犯病": mental,
    "/💈": mental,
    "/echo": echo,
    "/isbn": isbn,
    "/qr": qrcode,
    # "/meme": meme,
    "/quotation": quotation,
    "/q": quotation,
    "/stretch": stretch,
    "/parrot": parrot,
    "/url": get_url,
    "/ikun": ikun,
    "/mc": mc,
    "/uf": uf,
    "/pangu": pangu
}
admin_group_commands = {
    "/ban": ban,
    "/config": config_group,
}
su_private_commands = {"/enable": enable, "/disable": disable}
su_group_commands = {
    "/enable": enable,
    "/disable": disable,
    "/admin": admin,
}

with open("./data/mental.txt", encoding="utf-8") as f:
    mental_templates = f.readlines()


@bot.on_message("private")
async def handle_dm(event: Event):
    is_su = event.sender.get("user_id", 0) == SUPER_USER
    if enabled or is_su:
        msg = event.message
        cmd, left = msg_split(msg)
        if not (cmd and cmd.startswith("/")):
            return
        v = private_commands.get(cmd)
        if (not v) and is_su:
            v = su_private_commands.get(cmd)
        if v:
            config = get_config(v.__name__)
            if config.get("enabled", True) or is_su:
                await v(event, left)


@bot.on_message("group")
async def handle_msg(event: Event):
    admins = get_config("admin").get("list", [])
    is_su = event.sender.get("user_id", 0) == SUPER_USER
    is_admin = is_su or (event.sender.get("user_id", 0) in admins)
    if enabled or is_su:
        msg = event.message
        if get_config("bracket").get("enabled", True):
            s = msg_to_txt(msg)
            l = s.count("(") + s.count("（")
            r = s.count(")") + s.count("）")
            if l > r:
                await bot.send(event, ")" * (l - r))
        cmd, left = msg_split(msg)
        if not (cmd and cmd.startswith("/")):
            return
        v = group_commands.get(cmd)
        if (not v) and is_admin:
            v = admin_group_commands.get(cmd)
        if (not v) and is_su:
            v = su_group_commands.get(cmd)
        if v:
            config = get_config(v.__name__)
            if config.get("enabled", True) or is_su:
                await v(event, left)


@bot.on_request("group")
async def handle_group(event: Event):
    """Config `mode`: `accept`, `reject`, `all`.
    Config `invite`: `accept`, `reject`, `ignore`."""
    config = get_config()
    if event.sub_type == "add":
        flag = False
        m = search(r"答案：(\d+)", event.comment)
        if m:
            flag = valid(event.user_id, m.groups()[0], event.group_id)
        if config["mode"] == "accept":
            if flag:
                await bot.set_group_add_request(
                    flag=event.flag, sub_type="add", approve=True
                )
        elif config["mode"] == "reject":
            if not flag:
                await bot.set_group_add_request(
                    flag=event.flag,
                    sub_type="add",
                    approve=False,
                    reason=config["reason"],
                )
        elif config["mode"] == "all":
            await bot.set_group_add_request(
                flag=event.flag, sub_type="add", approve=flag, reason=config["reason"]
            )
    elif event.sub_type == "invite":
        if config["invite"] == "ignore":
            return
    else:
        print(f"Unexpected type: {event.sub_type}")


@bot.on_notice("notify")
async def handle_notice(event: Event):
    type_ = event.sub_type
    config = get_config("notify")
    if config["enabled"]:
        cf = config.get(type_)
        if cf and cf["enabled"]:
            qq = event.user_id if type_ != "lucky_king" else event.target_id
            if qq == event.self_id:
                return
            if type_ == "honor" and event.honor_type != "talkative":
                return
            reply = Message()
            msg = choice(cf["replies"]).split("@")
            if msg[0]:
                reply.append(MessageSegment.text(msg[0]))
            reply.append(MessageSegment.at(user_id=qq))
            if msg[1]:
                reply.append(MessageSegment.text(msg[1]))
            await bot.send(event, reply)


bot.run(host="127.0.0.1", port=PORT)
