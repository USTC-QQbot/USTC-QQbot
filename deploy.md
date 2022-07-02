# QQ 机器人部署
## 环境
### 系统
课程提供的 linux 虚拟机， Ubuntu 20.04.4 LTS 。

### Python & pip
Python 3.9, pip 22.1.2 。

## 部署
1. 新建目录，前往 [Github](https://github.com/Mrs4s/go-cqhttp/releases)下载对应系统版本的 `go-cqhttp` 压缩包并解压，参考其[说明文档](https://docs.go-cqhttp.org/guide/config.html#%E9%85%8D%E7%BD%AE%E4%BF%A1%E6%81%AF)进行初始化配置。以我所使用的系统为例：
    1. 下载文件： `wget https://github.com/Mrs4s/go-cqhttp/releases/download/v1.0.0-rc3/go-cqhttp_linux_amd64.tar.gz`
    2. 解压： `tar -xf go-cqhttp_linux_amd64.tar.gz`
    3. 运行可执行文件，选择 `反向WS` 项，此时目录下自动生成默认配置文件。
    4. 修改 `config.yml` 里 `message/post-format` 为 `array` 。
    5. 修改 `servers/ws-reverse/universal` 为 `ws://127.0.0.1:PORT/ws/` ，其中 `PORT` 为任意空闲端口。 
    6. 修改 `account/uin` 为 QQ 号。
    7. 配置文件可参考目录下的 `config.yml` 。
    8. 再次运行可执行文件，扫码登录。向机器人发送消息，即可在控制台看到输出。
    9. `Ctrl+C` 中断。
2. 安装依赖库 `pip install -r requirements.txt` 。
3. 修改 `config_override.json` 内的 `PORT` 为先前指定的端口号， `SUPER-USER` 为机器人的所有者 QQ 号， `CQ-PATH` 为 `go-cqhttp` 所在文件夹路径。

## 使用
1. 使用 `screen` 等命令保持 `./go-cqhttp` 后台运行。
2. 运行 `python3.9 bot.py` ，向提供的 QQ 号发送 `/help` 指令，即可收到回复。
