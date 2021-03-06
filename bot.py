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

from make_quotation import make_quotation
from stretch_image import make_stretch_image
from meme_recog import is_Capoo
from ustc_auth import valid
from ustc_covid import Covid
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
            return "???????????? - ????????? event ???"
        if event.detail_type == "group":
            group_id = event.group_id
        else:
            return "????????????????????????"
    if group_id >= 0:
        path = f"./group_config/{group_id}.json"
    else:
        return "???????????? - group_id ?????????"
    group_config = dict(full_config.get(group_id, {}))
    base_config = dict(full_config.get("base", {}))
    func_config = dict(base_config.get(func_name, {}))
    if not func_name in group_config:
        return "????????????????????????????????????"
    if option != None:
        func_config.update(group_config.get(func_name, {}))
        if option in base_config.get(func_name, {}):
            func_config[option] = base_config[func_name][option]
        else:
            return "????????? option ???"
        group_config[func_name] = func_config
    else:
        del group_config[func_name]
    full_config[group_id] = group_config
    with open(path, "w", encoding="utf-8") as f:
        dump(group_config, f, indent=4)
    return "???????????????"


def get_cred(qq: int):
    path = f"./credential/{qq}.json"
    if not isfile(path):
        cred = {}
    else:
        with open(path, encoding="utf-8") as f:
            cred: dict = load(f)
    return cred


async def can_ban(event: Event) -> bool:
    """???????????????????????????"""
    group_id = event.group_id
    sender = event.sender["user_id"]
    if sender == 80000000:
        return False
    self = await bot.get_group_member_info(group_id=group_id, user_id=event.self_id)
    sender = await bot.get_group_member_info(group_id=group_id, user_id=sender)
    if sender["role"] == "owner" or self["role"] == "member":
        return False
    elif self["role"] == "owner":
        return True
    else:
        return sender["role"] == "member"


async def roll(event, msg: Message):
    """??????????????????

    /roll - ????????????????????????????????? (?????? 1 ~ 6) ???????????????
    /roll <start> <end> - ?????? [<start>, <end>] ???????????????
    /roll *args - ??? args ????????????????????????
    """
    cmds = msg_to_txt(msg).split()
    if len(cmds) == 0:
        config = get_config()
        await bot.send(event, f"???????????? {randrange(config['start'], config['end'] + 1)} ???")
        return
    elif len(cmds) == 2:
        try:
            start, end = int(cmds[0]), (int(cmds[1]) + 1)
            result = randrange(start, end)
        except:
            result = choice()
    else:
        result = choice(cmds)
    await bot.send(event, f"???????????? {result} ???")


async def echo(event, msg: Message):
    """?????????????????????"""
    if len(msg):
        await bot.send(event, msg)


async def ban(event: Event, msg: Message):
    """?????????????????????

    /ban *@someone <duration> - ????????????????????? <duration>s ???
    a. ????????????????????????@??????????????????????????????
    b. <duration> ??????????????? 60 ???????????? 0 ??????????????????
    <reply> /ban <duration> - ?????????????????????????????????????????????????????????
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
    """????????????: /query <keyword> ???"""
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
    """?????? Latex ??????: /latex <formula> ???"""
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
            format=fname.split(".")[1],
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
    """?????????????????????????????????"""
    timestamp = int(time())
    time_ = strftime("%Y-%m-%d %H:%M:%S")
    await bot.send(event, f"???????????????{time_}\n????????????{timestamp}")


async def enable(event: Event, msg: Message):
    """??????????????????"""
    global enabled
    enabled = True
    await bot.send(event, "?????????????????????")


async def disable(event: Event, msg: Message):
    """??????????????????"""
    global enabled
    enabled = False
    await bot.send(event, "?????????????????????")


async def smart_question(event: Event, msg: Message):
    """????????????????????????????????????"""
    await bot.send(
        event,
        "?????????????????????\n  [??????]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/\n  [???/???]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way\n  [??????]??????: http://www.catb.org/~esr/faqs/smart-questions.html\n  [??????]???????????????https://ld246.com/article/1536732337028",
    )


async def wtf(event: Event, msg: Message):
    """RTFM/STFW ??????????????????"""
    await bot.send(
        event,
        "RTFM/STFW ??????????????????\n  [??????]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/#%E5%A6%82%E4%BD%95%E8%A7%A3%E8%AF%BB%E7%AD%94%E6%A1%88\n  [???/???]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way#rtfm%E5%92%8Cstfw%E5%A6%82%E4%BD%95%E7%9F%A5%E9%81%93%E4%BD%A0%E5%B7%B2%E5%AE%8C%E5%85%A8%E6%90%9E%E7%A0%B8%E4%BA%86\n  [??????]??????: http://www.catb.org/~esr/faqs/smart-questions.html#rtfm",
    )


async def isbn(event: Event, msg: Message):
    """??????????????? ISBN ????????????????????????"""
    serial = msg_to_txt(msg).partition(" ")[0]
    if not serial:
        await bot.send(event, "????????? ISBN ???")
        return
    config = get_config()
    key = config.get("apikey")
    if not key:
        await bot.send(event, "????????? apikey ?????")
        return
    r = get(f"https://api.jike.xyz/situ/book/isbn/{serial}", params={"apikey": key})
    if "isbn ??????!" in r.text:
        await bot.send(event, "ISBN ?????????")
        return
    data = r.json()
    if data["msg"] == "????????????":
        data = data["data"]
        msg_ = f'{data["name"]}\n?????????{data["author"]}\n????????????{data["publishing"]}\n???????????????{data["published"]}\n?????????{data["pages"]}\n?????????{data["price"]}\n?????????{data["description"]}'
        await bot.send(event, msg_)
    else:
        await bot.send(event, data["msg"])


async def qrcode(event: Event, msg: Message):
    """??????????????????"""
    data = msg_to_txt(msg)
    try:
        qr = make(data)
    except:
        await bot.send(event, "???????????????")
        return
    fname = f"qrcode_{time()}.png"
    path = CQ_PATH + "/data/images/" + fname
    qr.save(path)
    await bot.send(event, Message(MessageSegment.image(fname)))
    remove(path)


async def news(event: Event, msg: Message):
    """?????????????????????

    /news - ?????? 10 ??????????????????
    /news <i> - ????????? <i> ????????????????????????
    """
    arg = msg_to_txt(msg).strip()
    if not arg:
        await bot.send(event, request_rss(0))
    elif arg.isdigit():
        await bot.send(event, request_rss(0, int(arg)))
    else:
        await bot.send(event, "????????????????????????")


async def young(event: Event, msg: Message):
    """?????????????????????

    /young - ????????????????????????????????????
    /young all - ?????????????????????????????????
    * ???????????????????????? /cred ????????????????????? username ??? password ?????????????????????
    e.g. /cred username PBxxxxxxx, /cred password xxxxxx
    """
    cmds = msg_to_txt(msg).split()
    show_all = False
    if len(cmds) == 1 and cmds[0] == "all":
        show_all = True
    elif len(cmds) != 0:
        await bot.send(event, "???????????????")
        return
    sender = event.sender.get("user_id", 0)
    if not sender:
        return
    cred = get_cred(sender)
    username = cred.get("username", None)
    password = cred.get("password", None)
    if username == None or password == None:
        await bot.send(event, "???????????????")
        return
    clint = Young(username, password)
    res = clint.login()
    if not res[0]:
        await bot.send(event, res[1])
        return
    r = clint.get_activity(hide_entered=not show_all)
    await bot.send(event, r)


async def covid(event: Event, msg: Message):
    """???????????????????????????

    <????????????> + /covid - ??????????????????????????????????????????????????????????????????
    <????????????> + /covid trip - ??????????????????
    <????????????> + /covid report - ???????????????????????????
    /covid status - ???????????????????????????/??????????????????/...??????
    /covid checkin - ???????????????????????????????????????????????????
    /covid claim - ?????????????????????????????????????????????????????????
    * ???????????????????????????????????? cred ??? "covid_dest" ?????????????????????"covid_reason" ?????????????????????
    * ????????? /cred covid_dest ?????????, /cred covid_reason ??????/??????
    """
    cred = get_cred(event.sender.get("user_id"))
    for v in "username", "password", "covid_dest", "covid_reason":
        if not v in cred:
            await bot.send(event, f'???????????? "{v}"!')
            return
    cmds = msg_to_txt(msg).split()
    all_ = {"trip", "report", "status", "checkin", "claim"}
    if len(cmds) == 0:
        ops = ["checkin", "trip", "claim"]
        upload_pic = True
    elif len(cmds) == 1:
        if cmds[0] in all_:
            ops = [cmds[0]]
            upload_pic = cmds[0] in {"trip", "report"}
        else:
            await bot.send(event, "???????????????")
            return
    else:
        await bot.send(event, "???????????????")
        return
    if upload_pic:
        if len(msg):
            reply_seg = msg[0]
        else:
            await bot.send(event, "?????????????????????")
            return
        if reply_seg["type"] == "reply":
            try:
                replied = (await bot.get_msg(message_id=int(reply_seg["data"]["id"])))[
                    "message"
                ][0]
            except Exception as e:
                print(e)  # DEBUG
                await bot.send(event, "??????????????????????????????????????????QQ?????????")
                return
            url = replied["data"]["url"]
            img = get(url).content
            # await bot.send(event, url)
        else:
            await bot.send(event, "????????????????????????")
            return
    reply = []
    cov = Covid(cred["username"], cred["password"])
    r = cov.login()
    if not r[0]:
        reply.append("???????????????" + r[1])
    else:
        reply.append("???????????????")
    for op in ops:
        if op == "trip":
            r = cov.upload(img, 1)
            if not r[0]:
                reply.append("????????????????????????" + r[1])
            else:
                reply.append("????????????????????????")
        elif op == "report":
            r = cov.upload(img, 3)
            if not r[0]:
                reply.append("?????????????????????????????????" + r[1])
            else:
                reply.append("?????????????????????????????????")
        elif op == "status":
            reply.append("???????????????" + cov.status())
        elif op == "checkin":
            r = cov.checkin()
            if not r[0]:
                reply.append("???????????????" + r[1])
            else:
                reply.append("???????????????")
        elif op == "claim":
            r = cov.claim(cred["covid_dest"], cred["covid_reason"])
            if not r[0]:
                reply.append("???????????????" + r[1])
            else:
                reply.append("???????????????")
        else:
            return
    r = cov.logout()
    if not r:
        reply.append("???????????????")
    else:
        reply.append("???????????????")
    await bot.send(event, "\n".join(reply))


async def notice(event: Event, msg: Message):
    """?????????????????????

    /notice - ?????? 10 ??????????????????
    /notice <i> - ????????? <i> ????????????????????????
    """
    arg = msg_to_txt(msg).strip()
    if not arg:
        await bot.send(event, request_rss(1))
    elif arg.isdigit():
        await bot.send(event, request_rss(1, int(arg)))
    else:
        await bot.send(event, "????????????????????????")


async def turntable(event: Event, msg: Message):
    """?????????????????????"""
    config = get_config()
    sender = event.sender["user_id"]
    if sender == 80000000 or not await can_ban(event):
        await bot.send(event, "????????????????????????")
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
        await bot.send(event, "???????????????????????????{0}????????????{1}s???".format(nickname, duration))
    else:
        await bot.send(event, "{}????????????".format(nickname))
    if load:
        capacity = config["capacity"]
        bullets = config["bullets"]
        assert capacity >= bullets
        left = sample(range(1, capacity + 1), bullets)
        left.sort()
        await bot.send(event, "?????????????????????????????????")
    set_config("left", left)


async def meme(event: Event, msg: Message):
    """??????????????????????????????????????????"""
    if len(msg):
        reply_seg = msg[0]
    else:
        await bot.send(event, "?????????????????????")
        return
    if reply_seg["type"] == "reply":
        try:
            replied = (await bot.get_msg(message_id=int(reply_seg["data"]["id"])))[
                "message"
            ][0]
        except Exception as e:
            print(e)  # DEBUG
            await bot.send(event, "??????????????????????????????????????????QQ?????????")
            return
        url = replied["data"].get("url")
        if not url:
            await bot.send(event, "?????????????????????")
            return
    else:
        await bot.send(event, "?????????????????????")
        return
    result = is_Capoo(url, True)
    if result == 0:
        await bot.send(event, "???????????????")
        await bot.send(event, Message(MessageSegment.image("yes.gif")))
    elif result == 1:
        await bot.send(event, "??????????????????")
        await bot.send(event, Message(MessageSegment.image("no.gif")))
    else:
        await bot.send(event, "???????????????")
        await bot.send(event, Message(MessageSegment.image("error.gif")))


async def parrot(event: Event, msg: Message):
    '''????

    /parrot - ?????????????????? gif
    /parrot <name> - ??????????????? gif
    '''
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
        await bot.send(event, "???? not found!")
        return
    copyfile("./data/parrots/" + chosen, path)
    msg_ = Message(chosen[:-4])
    msg_.append(MessageSegment.image(fname))
    try:
        await bot.send(event, msg_)
    except exceptions.ActionFailed:
        await bot.send(event, chosen[:-4] + "???????????????")
    remove(path)


async def quotation(event: Event, msg: Message):
    '''???????????????'''
    if len(msg):
        reply_seg = msg[0]
    else:
        await bot.send(event, "?????????????????????")
        return
    if reply_seg["type"] == "reply":
        try:
            replied = (await bot.get_msg(message_id=int(reply_seg["data"]["id"])))
        except Exception as e:
            print(e)  # DEBUG
            await bot.send(event, "??????????????????????????????????????????QQ?????????")
            return
    else:
        await bot.send(event, "?????????????????????")
        return
    saying = msg_to_txt(replied['message'])
    sender = replied['sender']['user_id']
    avatar = get(f'http://q2.qlogo.cn/headimg_dl?dst_uin={sender}&spec=100').content
    info = await bot.get_group_member_info(group_id=event.group_id, user_id=sender)
    name = info["card"] if info["card"] else info["nickname"]
    try:
        img = make_quotation(avatar, saying, name)
    except ValueError as e:
        await bot.send(event, ', '.join(e.args))
        return
    fname = f'quotation_{time()}.jpg'
    path = CQ_PATH  + "/data/images/" + fname
    img.save(path)
    await bot.send(event, Message(MessageSegment.image(fname)))
    remove(path)


async def stretch(event: Event, msg: Message):
    '''??????????????????/stretch <text>'''
    text = msg_to_txt(msg)
    if not text:
        await bot.send(event, "??????????????????")
        return
    elif len(text) > 30:
        await bot.send(event, "??????????????????")
        return
    img = make_stretch_image(text)
    fname = f"stretch_{time()}.jpg"
    path = CQ_PATH  + "/data/images/" + fname
    img.save(path)
    await bot.send(event, Message(MessageSegment.image(fname)))
    remove(path)


async def mental(event: Event, msg: Message):
    """?????????

    /??????(????) - ?????????????????????
    /??????(????) txt/at - ????????????????????????"""
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


async def help(event: Event, msg: Message):
    """?????????????????????

    /help - ?????????????????????
    /help <func> - ?????? <func> ??????????????????
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
        await bot.send(event, "????????????: " + ", ".join(commands))
    elif command in commands:
        func = commands[command]
        await bot.send(
            event,
            func.__doc__.strip()
            if func.__doc__
            else "??????????????????????????????",
        )
    else:
        await bot.send(event, f'???????????? "{command}" ????????????')


async def admin(event: Event, msg: Message):
    """????????????????????????????????????

    /admin (list) - ?????????????????????????????????
    /admin add *@someone - ??????????????????????????????????????????
    /admin rm/del/remove *@someone - ??????????????????????????????????????????
    /admin clear - ?????????????????????????????????
    """
    cmds = msg_to_txt(msg).split()
    admins: list = get_config().get("list", [])
    mentioned = get_mentioned(msg)
    if not cmds:
        await bot.send(
            event, "???????????????????????????: " + (", ".join(map(str, admins)) if admins else "None")
        )
        return
    elif len(cmds) == 1:
        cmd = cmds[0]
        reply = "?"
        if cmd == "clear":
            admins = []
            reply = "????????????????????????????????????"
        elif cmd == "list":
            reply = "???????????????????????????: " + (", ".join(map(str, admins)) if admins else "None")
        elif cmd == "add":
            reply = "???????????????????????????????????????: "
            flag = False
            for candidate in mentioned:
                if candidate not in admins:
                    flag = True
                    admins.append(candidate)
                    reply += f"{candidate}, "
            if not flag:
                reply = "??????????????????????????????????????????"
            else:
                reply = reply[:-2]
        elif cmd in ("rm", "del", "remove"):
            reply = "???????????????????????????????????????: "
            flag = False
            for candidate in mentioned:
                if candidate in admins:
                    flag = True
                    admins.remove(candidate)
                    reply += f"{candidate}, "
            if not flag:
                reply = "??????????????????????????????????????????"
            else:
                reply = reply[:-2]
        set_config("list", admins)
        await bot.send(event, reply)
    else:
        await bot.send(event, "???????????????")


async def config_group(event: Event, msg: Message):
    """?????????????????????????????????

    /config <func> - ?????? <func> ??????????????????
    /config <func> <option> - ?????? <option> ???????????????
    /config <func> <option> <value> - ??? <option> ???????????? <value> ???
    /config unset <func> - ?????? <func> ??????????????????
    /config unset <func> <option> - ?????? <option> ?????????
    /config reload - ?????????????????????
    """
    cmds = msg_to_txt(msg).split()
    if not cmds:
        return
    if cmds[0] == "unset":
        if len(cmds) == 1:
            await bot.send(event, "???????????????")
            return
        elif len(cmds) == 2:
            ret = unset_config(cmds[1])
        elif len(cmds) == 3:
            ret = unset_config(cmds[1], cmds[2])
        else:
            await bot.send(event, "???????????????")
            return
        await bot.send(event, ret)
        return
    elif cmds[0] == "reload":
        load_config()
        await bot.send(event, "????????????????????????")
        return
    func = group_commands.get(("" if cmds[0].startswith("/") else "/") + cmds[0], None)
    if not func:
        await bot.send(event, "????????????????????????")
        return
    cmds[0] = func.__name__
    config = get_config(cmds[0])
    if len(cmds) == 1:
        await bot.send(event, dumps(config, ensure_ascii=False, indent=4))
    elif len(cmds) == 2:
        await bot.send(event, str(config.get(cmds[1])))
    elif len(cmds) == 3:
        option, value = cmds[1:]
        if value.isdigit():
            value = int(value)
        elif value.replace('.', '', 1).isdigit():
            value = float(value)
        if isinstance(value, str) and value.lower() in trans:
            trans = {"true": True, "false": False}
            value = trans[value.lower()]
        set_config(option, value, func_name=cmds[0])
        await bot.send(event, "???????????????")


async def credential(event: Event, msg: Message):
    """??????/???????????????????????????

    /cred - ????????????????????????????????????
    /cred <name> - ??????????????? <name> ????????????
    /cred <name> <value> - ??????/?????? <name> ????????? <value> ???
    /cred del <name> - ?????? <name> ?????????
    /cred del - ?????????????????????
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
            await bot.send(event, "???????????????")
            return
        else:
            await bot.send(
                event, "??????????????????" if not cmds[0] in cred else str(cred[cmds[0]])
            )
            return
    elif len(cmds) == 2:
        if cmds[0] == "del":
            if cmds[1] in cred:
                del cred[cmds[1]]
            else:
                await bot.send(event, "??????????????????")
                return
        else:
            cred[cmds[0]] = int(cmds[1]) if cmds[1].isdigit() else cmds[1]
    with open(path, "w", encoding="utf-8") as f:
        dump(cred, f, indent=4, ensure_ascii=False)
    await bot.send(event, "???????????????")


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
    "/covid": covid,
    "/isbn": isbn,
    "/qr": qrcode,
    "/meme": meme,
    "/stretch": stretch,
    "/parrot": parrot,
}
group_commands = {
    "/roll": roll,
    "/time": show_time,
    "/???????????????": smart_question,
    "/rtfm": wtf,
    "/stfw": wtf,
    "/query": query,
    "/help": help,
    "/latex": latex,
    "/news": news,
    "/notice": notice,
    "/????????????": turntable,
    "/??????": mental,
    "/????": mental,
    "/echo": echo,
    "/isbn": isbn,
    "/qr": qrcode,
    "/meme": meme,
    "/quotation": quotation,
    "/stretch": stretch,
    "/parrot": parrot,
}
admin_group_commands = {
    "/ban": ban,
    "/config": config_group,
}
su_private_commands = {"/enable": enable, "/disable": disable}
su_group_commands = {
    # "/ban": ban,
    "/enable": enable,
    "/disable": disable,
    "/admin": admin
    # "/config": config_group,
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
            l = s.count("(") + s.count("???")
            r = s.count(")") + s.count("???")
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
    COnfig `invite`: `accept`, `reject`, `ignore`."""
    config = get_config()
    if event.sub_type == "add":
        flag = False
        m = search(r"?????????(\d+)", event.comment)
        if m:
            flag = valid(event.user_id, m.groups()[0])
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
