# TweetSnapBot

基于 [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 的 Telegram 推文截图机器人。

设计目标：

- 入口只接受用户和机器人的私聊
- 每个 Telegram 用户可以绑定一个或多个“会话”
- 每个会话可以把截图投递到多个目标 chat
- 目标 chat 可以是群组、频道，或用户与机器人的私聊
- 配置方式保持和 `RuaBot` 类似，直接走环境变量
- 不依赖 TwitterShots；改为从 FxTwitter/FixupX 拉取推文元数据，并在本地渲染 PNG

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 环境变量

参考 [.env.example](/Users/cat0x1f/Documents/Repos/TweetSnapBot/.env.example)：

```bash
export BOT_TOKEN=123456789:telegram-bot-token
export FXTWITTER_API_BASE=https://api.fxtwitter.com
export LOG_LEVEL=INFO
export USER_SESSIONS='{"123456789":["default","ops"],"987654321":["default"]}'
export SESSIONS='{"default":{"targets":[123456789,-1001111111111],"theme":"light","format":"png"},"ops":{"targets":[-1002222222222],"theme":"dark","format":"png","show_views":false,"show_stats":false}}'
```

说明：

- `USER_SESSIONS`
  - key 是 Telegram 用户 ID
  - value 是该用户允许使用的会话名数组
- `SESSIONS`
  - key 是会话名
  - `targets` 是投递目标 chat id 数组
  - `theme`、`show_stats`、`show_timestamp`、`show_views` 等字段会影响本地渲染样式
- `FXTWITTER_API_BASE`
  - 可选，默认 `https://api.fxtwitter.com`
  - 当前实现通过这个接口拿 tweet 文本、作者和媒体数据
- `CAPTION_TEMPLATE`
  - 可选，自定义转发时的 caption
  - 可用变量：`{session}`、`{tweet_url}`、`{user_id}`、`{user_name}`、`{username}`

## 使用方式

用户只能私聊机器人发消息。

如果该用户只配置了一个会话，直接发送链接：

```text
https://x.com/OpenAI/status/1234567890123456789
```

如果该用户配置了多个会话，需要在消息第一个词写会话名：

```text
ops https://x.com/OpenAI/status/1234567890123456789
```

一条消息可以带多个链接，机器人会逐条截图并投递到该会话的所有目标 chat。

支持命令：

- `/start`
- `/help`
- `/sessions`

## 启动

```bash
python3 main.py
```

## 当前实现范围

- 支持 `x.com` / `twitter.com` 的 `status` 链接解析
- 通过 FxTwitter/FixupX 状态接口拉取 tweet 元数据
- 在本地用 Pillow 生成 PNG 卡片，不使用 Playwright
- 暂不包含 Dockerfile
- 暂不做数据库持久化；权限和路由全部来自环境变量
