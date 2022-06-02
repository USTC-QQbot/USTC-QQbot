from aiocqhttp import CQHttp, Event, Message, MessageSegment
from time import time, strftime
from random import randrange
from urllib.parse import quote
from inspect import currentframe, getframeinfo
from os.path import isfile
from json import load, dump, dumps


PORT = 4383
ADMIN = 364105900
bot = CQHttp()
enabled = True


def msg_to_txt(msg: Message) -> str:
    res = ""
    for seg in msg:
        if seg["type"] == "text":
            res += seg["data"]["text"]
    return res.strip()


def get_config(func_name: str='', group_id: int=0) -> dict:
    caller = currentframe().f_back
    if not func_name:
        func_name = getframeinfo(caller)[2]
    if not group_id:
        event = caller.f_locals.get('event')
        if not event:
            return {}
        if event.detail_type == 'group':
            group_id = event.group_id
            paths = ['config_base.json', f'./group_config/{group_id}.json', 'config_override.json']
        else:
            paths = ['config_base.json', 'config_override.json']
    config = {}
    for path in paths:
        if not isfile(path): continue
        with open(path) as f:
            config.update(load(f).get(func_name, {}))
    return config


def set_config(option: str, value, func_name: str='', group_id: int=0):
    '''Set the config.
    `group_id`: -1 for base, -2 for override, 0 for auto-retrieve.'''
    caller = currentframe().f_back
    if not func_name:
        func_name = getframeinfo(caller)[2]
    if not group_id:
        event = caller.f_locals.get('event')
        if not event:
            return
        if event.detail_type == 'group':
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
    with open(path, encoding="utf-8") as f:
        config_full = load(f)
    if not config_full.get(func_name):
        config_full[func_name] = {}
    config_full[func_name][option] = value
    with open(path, "w", encoding="utf-8") as f:
        dump(config_full, f, indent=4)


async def roll(event, msg: Message):
    cmds = msg_to_txt(msg).split()
    if len(cmds) == 1:
        config = get_config()
        await bot.send(event, f"你摇到了 {randrange(config['start'], config['end'] + 1)} ！")
        return
    try:
        start, end = int(cmds[1]), int(cmds[2])
        result = randrange(start, end)
    except:
        await bot.send(event, "参数错误！")
    else:
        await bot.send(event, f"你摇到了 {result} ！")


async def ban(event: Event, msg: Message):
    qqs = set()
    duration = 60
    for seg in msg:
        if seg["type"] == "at":
            qqs.add(seg["data"]["qq"])
        elif seg["type"] == "text":
            try:
                duration = int(seg["data"]["text"].strip())
            except:
                pass
    if "all" in qqs:
        await bot.set_group_whole_ban(group_id=event.group_id, enable=bool(duration))
        return
    for qq in qqs:
        await bot.set_group_ban(
            group_id=event.group_id, user_id=int(qq), duration=duration
        )


async def email(event: Event, msg: Message):
    cmd = msg_to_txt(msg)
    cmds = cmd.split()
    if len(cmds) == 1:
        await bot.send(event, "参数不足！")
        return
    teacher = cmds[1]
    await bot.send(
        event,
        f"{teacher}老师的搜索结果：https://cn.bing.com/search?q={quote(teacher)}+site%3Austc.edu.cn",
    )


async def show_time(event: Event, msg: Message):
    timestamp = int(time())
    time_ = strftime("%Y-%m-%d %H:%M:%S")
    await bot.send(event, f"当前时间：{time_}\n时间戳：{timestamp}")


async def enable(event: Event, msg: Message):
    global enabled
    enabled = True
    await bot.send(event, "机器人已启用。")


async def disable(event: Event, msg: Message):
    global enabled
    enabled = False
    await bot.send(event, "机器人已禁用。")


async def smart_question(event: Event, msg: Message):
    await bot.send(
        event,
        "《提问的智慧》\n  [简中]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/\n  [繁/简]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way\n  [英语]原文: http://www.catb.org/~esr/faqs/smart-questions.html\n  [简中]思维导图：https://ld246.com/article/1536732337028",
    )


async def wtf(event: Event, msg: Message):
    await bot.send(
        event,
        "RTFM/STFW 是什么意思？\n  [简中]USTC LUG: https://lug.ustc.edu.cn/wiki/doc/smart-questions/#%E5%A6%82%E4%BD%95%E8%A7%A3%E8%AF%BB%E7%AD%94%E6%A1%88\n  [繁/简]Github: https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way#rtfm%E5%92%8Cstfw%E5%A6%82%E4%BD%95%E7%9F%A5%E9%81%93%E4%BD%A0%E5%B7%B2%E5%AE%8C%E5%85%A8%E6%90%9E%E7%A0%B8%E4%BA%86\n  [英语]原文: http://www.catb.org/~esr/faqs/smart-questions.html#rtfm",
    )


async def help(event: Event, msg: Message):
    is_admin = (event.sender.get("user_id", 0) == ADMIN)
    if event.detail_type == 'group':
        commands = group_commands
        if is_admin:
            commands.update(admin_group_commands)
    elif event.detail_type == 'private':
        commands = private_commands
        if is_admin:
            commands.update(admin_private_commands)
    await bot.send(event, "当前可用指令：" + ', '.join(commands))


async def config_group(event: Event, msg: Message):
    '''/config <func> (<option> (<value>))'''
    cmds = msg_to_txt(msg).split()[1:]
    if not cmds:
        return
    func = group_commands.get(('' if cmds[0].startswith('/') else '/') + cmds[0], None)
    if not func: return
    cmds[0] = func.__name__
    config = get_config(cmds[0])
    if len(cmds) == 1:
        await bot.send(event, dumps(config, ensure_ascii=False, indent=4))
    elif len(cmds) == 2:
        await bot.send(event, str(config.get(cmds[1])))
    elif len(cmds) == 3:
        option, value = cmds[1:]
        trans = {'true': True, 'false': False}
        if value.lower() in trans:
            value = trans[value.lower()]
        set_config(option, value, func_name=cmds[0])
        await bot.send(event, "Success.")


private_commands = {"/roll": roll, "/time": show_time, "/email": email, "/help": help}
group_commands = {
    "/roll": roll,
    "/time": show_time,
    "/提问的智慧": smart_question,
    "/rtfm": wtf,
    "/stfw": wtf,
    "/email": email,
    "/help": help
}
admin_private_commands = {"/enable": enable, "/disable": disable}
admin_group_commands = {"/ban": ban, "/enable": enable, "/disable": disable, "/config": config_group}


@bot.on_message("private")
async def handle_dm(event: Event):
    is_admin = (event.sender.get("user_id", 0) == ADMIN)
    if enabled or is_admin:
        msg: Message = event.message
        cmd = msg_to_txt(msg)
        if not cmd:
            return
        for k, v in private_commands.items():
            if cmd.startswith(k + ' ') or cmd == k:
                await v(event, msg)
                return
        if not is_admin:
            return
        for k, v in admin_private_commands.items():
            if cmd.startswith(k + ' ') or cmd == k:
                await v(event, msg)
                return


@bot.on_message("group")
async def handle_msg(event: Event):
    is_admin = (event.sender.get("user_id", 0) == ADMIN)
    if enabled or is_admin:
        msg: Message = event.message
        cmd = msg_to_txt(msg)
        if not cmd:
            return
        for k, v in group_commands.items():
            if cmd.startswith(k + ' ') or cmd == k:
                config = get_config(v.__name__)
                if config.get('enabled', True):
                    await v(event, msg)
                return
        if not is_admin:
            return
        for k, v in admin_group_commands.items():
            if cmd.startswith(k + ' ') or cmd == k:
                await v(event, msg)
                return


bot.run(host="127.0.0.1", port=PORT)

