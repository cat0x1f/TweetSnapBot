# TweetSnapBot

基于 [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) 的 Telegram 推文截图机器人。

设计目标：

- 入口只接受用户和机器人的私聊
- 机器人使用单套全局配置，把截图投递到多个目标 chat
- 目标 chat 可以是群组、频道，或用户与机器人的私聊
- 配置方式保持和 `RuaBot` 类似，直接走环境变量
- 不依赖 TwitterShots；改为从 FxTwitter/FixupX 拉取推文元数据，并在本地渲染 PNG


## 环境变量

```bash
export BOT_TOKEN=123456789:telegram-bot-token
export FXTWITTER_API_BASE=https://api.fxtwitter.com
export LOG_LEVEL=INFO
export ADMIN_USER_IDS='[123456789]'
export TARGETS='[123456789,-1001111111111]'
export THEME=light
export FORMAT=png
export SHOW_VIEWS=true
export SHOW_STATS=true
```

说明：

- `ADMIN_USER_IDS`
  - 可选，JSON 数组
  - 允许使用机器人的 Telegram 用户 ID 列表
- `TARGETS`
  - 必填，JSON 数组
  - 表示截图投递目标 chat id 列表
- `THEME`、`LOGO`、`FORMAT`、`SHOW_FULL_TEXT`、`SHOW_STATS`、`SHOW_TIMESTAMP`、`SHOW_VIEWS`
  - 可选，全局渲染配置
- `CONTAINER_BACKGROUND`、`CONTAINER_PADDING`、`BORDER_RADIUS`、`BACKGROUND_IMAGE`
  - 可选，卡片容器样式配置
- `FXTWITTER_API_BASE`
  - 可选，默认 `https://api.fxtwitter.com`
  - 当前实现通过这个接口拿 tweet 文本、作者和媒体数据
- `CAPTION_TEMPLATE`
  - 可选，自定义转发时的 caption
  - 可用变量：`{tweet_url}`、`{user_id}`、`{user_name}`、`{username}`

## 使用方式

用户只能私聊机器人发消息。
只有 `ADMIN_USER_IDS` 中的用户可以使用机器人。

直接发送链接：

```text
https://x.com/OpenAI/status/1234567890123456789
```

一条消息可以带多个链接，机器人会逐条截图并投递到所有目标 chat。

支持命令：

- `/start`
- `/help`

## 启动

```bash
python3 main.py
```

## 当前实现范围

- 支持 `x.com` / `twitter.com` 的 `status` 链接解析
- 通过 FxTwitter/FixupX 状态接口拉取 tweet 元数据
- 在本地用 Pillow 生成 PNG 卡片，不使用 Playwright
- 暂不做数据库持久化；投递目标和渲染配置全部来自环境变量
