from aiocqhttp import CQHttp, Event, Message, MessageSegment
from time import time, strftime
from random import randrange, random
from urllib.parse import quote
from inspect import currentframe, getframeinfo
from os import remove, listdir
from os.path import isfile
from json import load, dump, dumps
import matplotlib.pyplot as plt
from matplotlib import rcParams
from re import search
from ustc_auth import valid
from ustc_news import request_rss
from ustc_young import Young


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


def load_config():
    global full_config
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


async def can_ban(event: Event) -> bool:
    """是否能够禁言发送者"""
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
    """生成随机数。

    /roll - 生成配置文件中指定范围 (默认 1 ~ 6) 的随机数。
    /roll <start> <end> - 生成 [<start>, <end>] 的随机数。
    """
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
    """禁言指定用户。

    /ban *@someone <duration> - 禁言提及的人员 <duration>s 。
    a. 可指定多位成员，@全体成员则全体禁言。
    b. <duration> 未指定则为 60 ，指定为 0 则取消禁言。
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
        await bot.set_group_ban(group_id=event.group_id, user_id=qq, duration=duration)


async def query(event: Event, msg: Message):
    """站内搜索: /query <keyword> 。"""
    config = get_config()
    cmd = msg_to_txt(msg)
    cmds = cmd.split()
    if len(cmds) == 1:
        await bot.send(event, config["insufficient"])
        return
    teacher = cmds[1]
    url = config["engine"].format(quote(teacher))
    await bot.send(event, config["format"].format(teacher, url))


async def latex(event: Event, msg: Message):
    """渲染 Latex 公式: /latex <formula> 。"""
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


async def news(event: Event, msg: Message):
    """获取科大要闻。

    /news - 获取 10 条科大要闻。
    /news <i> - 查看第 <i> 条的摘要与链接。
    """
    arg = msg_to_txt(msg).removeprefix("/news").strip()
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
    if len(cmds) == 2 and cmds[1] == 'all':
        show_all = True
    elif len(cmds) != 1:
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
    arg = msg_to_txt(msg).removeprefix("/notice").strip()
    if not arg:
        await bot.send(event, request_rss(1))
    elif arg.isdigit():
        await bot.send(event, request_rss(1, int(arg)))
    else:
        await bot.send(event, "请传入合法参数！")


async def turntable(event: Event, msg: Message):
    """随机决定是否禁言指定范围内的一段时间。"""
    config = get_config()
    sender = event.sender["user_id"]
    if not await can_ban(event):
        await bot.send(event, config["reject"])
        return
    nickname = await bot.get_group_member_info(group_id=event.group_id, user_id=sender)
    nickname = nickname["nickname"]
    if random() < config["probability"]:
        duration = randrange(config["min"], config["max"] + 1)
        await bot.set_group_ban(
            group_id=event.group_id, user_id=sender, duration=duration
        )
        await bot.send(event, config["prompt_ban"].format(nickname, duration))
    else:
        await bot.send(event, config["prompt_safe"].format(nickname))


async def help(event: Event, msg: Message):
    """显示帮助信息。

    /help - 列出可用指令。
    /help <func> - 展示 <func> 的帮助信息。
    """
    command = "/" + msg_to_txt(msg).removeprefix("/help").strip().removeprefix("/")
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
    if command == "/":
        await bot.send(event, "可用指令: " + ", ".join(commands))
    elif command in commands:
        func = commands[command]
        await bot.send(
            event,
            f"函数名: {func.__name__}\n" + func.__doc__.strip()
            if func.__doc__
            else "此指令没有帮助信息。",
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
    /config unset <func> - 重置 <func> 的群组配置。
    /config unset <func> <option> - 重置 <option> 的值。
    /config reload - 重新加载配置。
    """
    cmds = msg_to_txt(msg).split()[1:]
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
    func = group_commands.get(("" if cmds[0].startswith("/") else "/") + cmds[0], None)
    if not func:
        await bot.send(event, "未找到指定函数。")
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
        if value.isdigit():
            value = int(value)
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
    cmds = msg_to_txt(msg).split()[1:]
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
rcParams["text.latex.preamble"] = r"\usepackage{amsmath}"

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
    "/notice": notice,
    "/毛子转盘": turntable,
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
