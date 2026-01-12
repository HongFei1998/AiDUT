# 🤖 AI 手机助手 (aiDut)

使用自然语言控制 Android 手机的智能助手。通过大语言模型理解用户意图，结合 OCR 识别屏幕内容，自动执行点击、滑动、输入等操作，实现手机自动化控制。

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0+-green.svg)
![uiautomator2](https://img.shields.io/badge/uiautomator2-3.5+-orange.svg)

## ✨ 功能特性

- 🗣️ **自然语言控制** - 用自然语言描述任务，AI 自动理解并执行
- 📱 **实时屏幕同步** - 实时显示手机屏幕，可视化操作过程
- 🔍 **智能 OCR 识别** - 自动识别屏幕文字内容，辅助 AI 决策
- 🔄 **Agent 循环执行** - 自动分析-决策-执行，无需人工干预
- 📶 **无线调试支持** - 支持 Android 11+ 无线调试，扫码即连
- ⚡ **并行优化** - 并行获取截图、UI层级、OCR，提升响应速度
- 🛑 **任务中断** - 支持随时停止正在执行的任务

## 🖥️ 界面预览

```
┌─────────────────────────────────────────────────────────────┐
│  📱 AI 手机助手                            [🔴 未连接] [连接设备] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌───────────────┐      ┌─────────────────────────────┐   │
│   │               │      │ 🤖 你好！我是你的AI手机助手      │   │
│   │    设备屏幕    │      │                             │   │
│   │               │      │ 告诉我你想在手机上做什么，     │   │
│   │               │      │ 我来帮你完成。               │   │
│   │               │      │                             │   │
│   │               │      │ [打开微信] [截图保存] [返回桌面]   │   │
│   │               │      │                             │   │
│   └───────────────┘      ├─────────────────────────────┤   │
│                          │ 描述你想执行的任务...    [发送]  │   │
│                          └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Android 设备 (需开启 USB 调试)
- ADB 工具 (需添加到系统 PATH)
- OpenAI API Key (或兼容的大模型 API)

### 安装步骤

1. **克隆项目**

```bash
git clone <repo-url>
cd aiDut
```

2. **安装依赖**

```bash
pip install -r requirements.txt
```

3. **配置环境变量**

创建 `.env` 文件：

```env
# 大模型配置
LLM_API_KEY=your-api-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# Flask 配置
SECRET_KEY=your-secret-key
DEBUG=True

# 可选：指定设备序列号
DEVICE_SERIAL=
```

4. **连接 Android 设备**

```bash
# 确认设备已连接
adb devices
```

5. **启动服务**

```bash
python run.py
```

6. **访问 Web 界面**

打开浏览器访问：http://localhost:5000

## 📖 使用指南

### 连接设备

支持两种连接方式：

#### USB 连接
1. 用 USB 数据线连接手机和电脑
2. 确保手机已开启 USB 调试
3. 点击「连接设备」按钮选择设备

#### 无线调试 (Android 11+)
1. 手机开启 **设置 → 开发者选项 → 无线调试**
2. 点击「无线调试」选项卡
3. 点击「生成配对二维码」
4. 在手机上选择「使用二维码配对设备」扫描

### 执行任务

在输入框中输入任务描述，例如：

- "打开微信，搜索'张三'，发送消息'你好'"
- "打开设置，调低屏幕亮度"
- "打开相机拍一张照片"
- "打开抖音，向上滑动看下一个视频"

AI 会自动：
1. 截取屏幕并识别内容
2. 分析当前状态与任务目标
3. 决定下一步操作
4. 执行操作并循环直到任务完成

### 手动控制

- 点击屏幕预览可直接点击对应位置
- 底部导航按钮：◀ 返回 / ● 主页 / ▣ 最近任务

## 📁 项目结构

```
aiDut/
├── run.py                 # 启动入口
├── config.py              # 配置文件
├── requirements.txt       # 依赖列表
├── app/
│   ├── __init__.py        # Flask 应用初始化
│   ├── routes/            # API 路由
│   │   ├── main.py        # 主页路由
│   │   ├── device.py      # 设备相关 API
│   │   └── chat.py        # 对话/任务 API
│   ├── services/          # 业务逻辑
│   │   ├── agent_service.py    # Agent 核心服务
│   │   ├── device_service.py   # 设备控制服务
│   │   ├── llm_service.py      # 大模型服务
│   │   ├── ocr_service.py      # OCR 识别服务
│   │   ├── preset_service.py   # 预设管理服务
│   │   ├── wireless_service.py # 无线调试服务
│   │   └── presets.json        # 预设配置
│   ├── static/            # 静态资源
│   │   ├── css/style.css
│   │   └── js/main.js
│   └── templates/         # HTML 模板
│       └── index.html
```

## 🔧 API 接口

### 设备相关

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/device/list` | GET | 获取设备列表 |
| `/api/device/connect` | POST | 连接设备 |
| `/api/device/disconnect` | POST | 断开连接 |
| `/api/device/screenshot` | GET | 获取截图 |
| `/api/device/info` | GET | 获取设备信息 |

### 任务执行

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat/execute` | POST | 执行任务 (SSE 流式返回) |
| `/api/chat/stop` | POST | 停止任务 |
| `/api/chat/single-action` | POST | 执行单个操作 |
| `/api/chat/settings` | GET/POST | 获取/更新设置 |

## ⚙️ 配置说明

### Agent 设置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `max_steps` | 50 | 最大执行步数 |
| `action_delay` | 0.8s | 操作后等待时间 |
| `skip_ui_hierarchy` | false | 是否跳过 UI 层级获取 |
| `parallel_enabled` | true | 是否启用并行获取 |

### 支持的操作类型

- `click` - 点击坐标
- `swipe` - 滑动 (支持方向: up/down/left/right)
- `input` - 输入文字
- `press` - 按键 (home/back/recent 等)
- `wait` - 等待
- `start_app` - 启动应用

## 🛠️ 技术架构

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Web 前端   │ ←→  │  Flask 后端  │ ←→  │  Android 设备 │
│  (HTML/JS)   │     │   (Python)   │     │ (uiautomator2)│
└──────────────┘     └──────┬───────┘     └──────────────┘
                           │
                    ┌──────┴───────┐
                    │   LLM API    │
                    │ (GPT-4o等)   │
                    └──────────────┘
```

**核心流程：**
1. 用户输入自然语言任务
2. 获取设备截图 + OCR 识别
3. 发送给 LLM 分析决策
4. 执行 LLM 返回的操作
5. 循环直到任务完成

### Q: 支持哪些手机？
A: 理论上支持所有 Android 设备，推荐 Android 7.0 及以上版本。

## 📄 开源协议

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！
