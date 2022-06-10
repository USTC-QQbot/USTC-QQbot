import matplotlib.pyplot as plt
from matplotlib import rcParams
from aiocqhttp import CQHttp, Event, Message, MessageSegment
from time import time, strftime
from random import randrange
from urllib.parse import quote
from inspect import currentframe, getframeinfo
from os import remove
from os.path import isfile
from json import load, dump, dumps
from re import search
from ustc_auth import valid
from ustc_news import request_rss

with open("config_override.json") as f:
    config = load(f)
PORT: int = config["PORT"]
SUPER_USER: int = config["SUPER-USER"]
CQ_PATH: str = config["CQ-PATH"]
del config
bot = CQHttp()
enabled = True
rcParams["text.usetex"] = True
rcParams["text.latex.preamble"] = r"\usepackage{amsmath}"


def msg_to_txt(msg: Message) -> str:
    res = ""
    for seg in msg:
        if seg["type"] == "text":
            res += seg["data"]["text"]
    return res.strip()


def get_mentioned(msg: Message) -> set:
    mentioned = set()
    for seg in msg:
        if seg["type"] == "at":
            mentioned.add(seg["data"]["qq"])
    return set(map(int, mentioned))


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
            paths = [
                "config_base.json",
                f"./group_config/{group_id}.json",
                "config_override.json",
            ]
        else:
            paths = ["config_base.json", "config_override.json"]
    config = {}
    for path in paths:
        if not isfile(path):
            continue
        with open(path) as f:
            config.update(load(f).get(func_name, {}))
    return config


def set_config(option: str, value, func_name: str = "", group_id: int = 0):
    """Set the config.
    `group_id`: -1 for base, -2 for override, 0 for auto-retrieve."""
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
    elif group_id == -1:
        path = "./config_base.json"
    elif group_id == -2:
        path = "./config_override.json"
    else:
        return
    if not isfile(path):
        config_full = {}
    else:
        with open(path, encoding="utf-8") as f:
            config_full = load(f)
    if not config_full.get(func_name):
        config_full[func_name] = {}
    config_full[func_name][option] = value
    with open(path, "w", encoding="utf-8") as f:
        dump(config_full, f, indent=4)


async def roll(event, msg: Message):
    '''生成随机数。

    /roll - 生成配置文件中指定范围 (默认 1 ~ 6) 的随机数。
    /roll <start> <end> - 生成 [<start>, <end>] 的随机数。
    '''
    cmds = msg_to_txt(msg).split()
    if len(cmds) == 1:
        config = get_config()
        await bot.send(event, f"你摇到了 {randrange(config['start'], config['end'] + 1)} ！")
        return
    try:
        start, end = int(cmds[1]), (int(cmds[2]) + 1)
        result = randrange(start, end)
    except:
        await bot.send(event, "参数错误！")
    else:
        await bot.send(event, f"你摇到了 {result} ！")


async def ban(event: Event, msg: Message):
    '''禁言指定用户。

    /ban *@someone <duration> - 禁言提及的人员 <duration>s 。
    a. 可指定多位成员，@全体成员则全体禁言。
    b. <duration> 未指定则为 60 ，指定为 0 则取消禁言。
    '''
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
    if "all" in qqs:
        await bot.set_group_whole_ban(group_id=event.group_id, enable=bool(duration))
        return
    for qq in qqs:
        await bot.set_group_ban(group_id=event.group_id, user_id=qq, duration=duration)


async def query(event: Event, msg: Message):
    '''站内搜索: /query <keyword> 。'''
    config = get_config()
    cmd = msg_to_txt(msg)
    cmds = cmd.split()
    if len(cmds) == 1:
        await bot.send(event, config['insufficient'])
        return
    teacher = cmds[1]
    url = config['engine'].format(quote(teacher))
    await bot.send(
        event,
        config['format'].format(teacher, url)
    )


async def latex(event: Event, msg: Message):
    '''渲染 Latex 公式: /latex <formula> 。'''
    formula = msg_to_txt(msg).removeprefix("/latex").strip()
    if not formula:
        return
    formula_ = f"${formula}$"
    fig = plt.figure(figsize=(0.01, 0.01))
    fig.text(0, 0, formula_, fontsize=18)
    fname = f"latex_{int(time())}.png"
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
    await bot.send(
        event, Message(MessageSegment.image(fname))
    )
    remove(path)


async def show_time(event: Event, msg: Message):
    '''发送当前时间及时间戳。'''
    timestamp = int(time())
    time_ = strftime("%Y-%m-%d %H:%M:%S")
    await bot.send(event, f"当前时间：{time_}\n时间戳：{timestamp}")


async def enable(event: Event, msg: Message):
    '''启用机器人。'''
    global enabled
    enabled = True
    await bot.send(event, "机器人已启用。")


async def disable(event: Event, msg: Message):
    '''禁用机器人。'''
    global enabled
    enabled = False
    await bot.send(event, "机器人已禁用。")


async def smart_question(event: Event, msg: Message):
    '''发送《提问的智慧》链接。'''
    await bot.send(
        event,
        "《提问的智慧》\n  [简中]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/\n  [繁/简]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way\n  [英语]原文: http://www.catb.org/~esr/faqs/smart-questions.html\n  [简中]思维导图：https://ld246.com/article/1536732337028",
    )


async def wtf(event: Event, msg: Message):
    '''RTFM/STFW 是什么意思？'''
    await bot.send(
        event,
        "RTFM/STFW 是什么意思？\n  [简中]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/#%E5%A6%82%E4%BD%95%E8%A7%A3%E8%AF%BB%E7%AD%94%E6%A1%88\n  [繁/简]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way#rtfm%E5%92%8Cstfw%E5%A6%82%E4%BD%95%E7%9F%A5%E9%81%93%E4%BD%A0%E5%B7%B2%E5%AE%8C%E5%85%A8%E6%90%9E%E7%A0%B8%E4%BA%86\n  [英语]原文: http://www.catb.org/~esr/faqs/smart-questions.html#rtfm",
    )


async def news(event: Event, msg: Message):
    '''获取科大要闻。

    /news - 获取 10 条科大要闻。
    /news <i> - 查看第 <i> 条的摘要与链接。
    '''
    arg = msg_to_txt(msg).removeprefix('/news').strip()
    if not arg:
        await bot.send(event, request_rss(0))
    elif arg.isdigit():
        await bot.send(event, request_rss(0, int(arg)))
    else:
        await bot.send(event, "请传入合法参数！")


async def notice(event: Event, msg: Message):
    '''获取通知公告。

    /notice - 获取 10 条通知公告。
    /notice <i> - 查看第 <i> 条的摘要与链接。
    '''
    arg = msg_to_txt(msg).removeprefix('/notice').strip()
    if not arg:
        await bot.send(event, request_rss(1))
    elif arg.isdigit():
        await bot.send(event, request_rss(1, int(arg)))
    else:
        await bot.send(event, "请传入合法参数！")


async def help(event: Event, msg: Message):
    '''显示帮助信息。

    /help - 列出可用指令。
    /help <func> - 展示 <func> 的帮助信息。
    '''
    command = '/' + msg_to_txt(msg).removeprefix('/help').strip().removeprefix('/')
    admins = get_config("admin").get("list", [])
    is_su = event.sender.get("user_id", 0) == SUPER_USER
    is_admin = is_su or (event.sender.get("user_id", 0) in admins)
    if event.detail_type == "group":
        commands = dict(group_commands)
        if is_admin:
            commands.update(admin_group_commands)
        if is_su:
            commands.update(su_group_commands)
    elif event.detail_type == "private":
        commands = dict(private_commands)
        if is_su:
            commands.update(su_private_commands)
    if command == '/':
        await bot.send(event, "可用指令: " + ", ".join(commands))
    elif command in commands:
        func = commands[command]
        await bot.send(event, func.__doc__.strip() if func.__doc__ else "此指令没有帮助信息。")
    else:
        await bot.send(event, f'没有名为 "{command}" 的指令。')


async def admin(event: Event, msg: Message):
    '''控制群聊的机器人管理员。

    /admin (list) - 列出所有机器人管理员。
    /admin add *@someone - 把提及的人设为机器人管理员。
    /admin rm/del/remove *@someone - 把提及的人移出机器人管理员。
    /admin clear - 移除所有机器人管理员。
    '''
    cmds = msg_to_txt(msg).split()[1:]
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
    """
    cmds = msg_to_txt(msg).split()[1:]
    if not cmds:
        return
    func = group_commands.get(("" if cmds[0].startswith("/") else "/") + cmds[0], None)
    if not func:
        return
    cmds[0] = func.__name__
    config = get_config(cmds[0])
    if len(cmds) == 1:
        await bot.send(event, dumps(config, ensure_ascii=False, indent=4))
    elif len(cmds) == 2:
        await bot.send(event, str(config.get(cmds[1])))
    elif len(cmds) == 3:
        option, value = cmds[1:]
        trans = {"true": True, "false": False}
        if value.lower() in trans:
            value = trans[value.lower()]
        set_config(option, value, func_name=cmds[0])
        await bot.send(event, "操作成功。")


private_commands = {
    "/roll": roll,
    "/time": show_time,
    "/query": query,
    "/help": help,
    "/latex": latex,
    "/news": news,
    "/notice": notice
}
group_commands = {
    "/roll": roll,
    "/time": show_time,
    "/提问的智慧": smart_question,
    "/rtfm": wtf,
    "/stfw": wtf,
    "/query": query,
    "/help": help,
    "/latex": latex,
    "/news": news,
    "/notice": notice
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


@bot.on_message("private")
async def handle_dm(event: Event):
    is_su = event.sender.get("user_id", 0) == SUPER_USER
    if enabled or is_su:
        msg: Message = event.message
        cmd = msg_to_txt(msg)
        if not cmd:
            return
        for k, v in private_commands.items():
            if cmd.startswith(k + " ") or cmd == k:
                await v(event, msg)
                return
        if not is_su:
            return
        for k, v in su_private_commands.items():
            if cmd.startswith(k + " ") or cmd == k:
                await v(event, msg)
                return


@bot.on_message("group")
async def handle_msg(event: Event):
    admins = get_config("admin").get("list", [])
    is_su = event.sender.get("user_id", 0) == SUPER_USER
    is_admin = is_su or (event.sender.get("user_id", 0) in admins)
    if enabled or is_su:
        msg: Message = event.message
        cmd = msg_to_txt(msg)
        if not cmd:
            return
        for k, v in group_commands.items():
            if cmd.startswith(k + " ") or cmd == k:
                config = get_config(v.__name__)
                if config.get("enabled", True):
                    await v(event, msg)
                return
        if not is_admin:
            return
        for k, v in admin_group_commands.items():
            if cmd.startswith(k + " ") or cmd == k:
                await v(event, msg)
                return
        if not is_su:
            return
        for k, v in su_group_commands.items():
            if cmd.startswith(k + " ") or cmd == k:
                await v(event, msg)
                return


@bot.on_request("group")
async def handle_group(event: Event):
    """Config `mode`: `accept`, `reject`, `all`.
    COnfig `invite`: `accept`, `reject`, `ignore`."""
    config = get_config()
    if event.sub_type == "add":
        flag = False
        m = search(r"答案：(\d+)", event.comment)
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


bot.run(host="127.0.0.1", port=PORT)
