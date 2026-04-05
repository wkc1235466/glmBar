# GlmBar Python 版本

## 项目概述

GlmBar 是一个系统托盘桌面应用，用于监控多个 AI 编程套餐的用量额度。Python 版本基于 **PySide6 (Qt6)** 构建。

## 技术栈

| 组件 | 技术 |
|------|------|
| GUI 框架 | PySide6 >= 6.8 (Qt6) |
| HTTP 客户端 | httpx >= 0.28 (异步) |
| 数据验证 | pydantic >= 2.10 |
| Cookie 解析 | rookiepy >= 0.5.6 |
| Python 版本 | >= 3.11 |
| 包管理器 | uv |

## 项目结构

```
├── main.py                    # 入口文件，GlmBarApp 主控制器
├── pyproject.toml             # 项目配置与依赖
├── src/
│   ├── config/
│   │   └── settings.py        # 配置管理 (Pydantic 模型 + JSON 存储)
│   ├── providers/             # AI 服务提供商
│   │   ├── base.py            # BaseProvider 抽象基类、UsageData、ProviderRegistry
│   │   ├── zai.py             # 智谱 (Z.ai / BigModel)
│   │   ├── minimax.py         # MiniMax
│   │   ├── kimi.py            # Kimi (月之暗面)
│   │   ├── alibaba.py         # 阿里云百炼
│   │   ├── openrouter.py      # OpenRouter
│   │   ├── baidu.py           # 百度千帆 (Cookie 认证)
│   │   └── custom.py          # 自定义 HTTP API
│   ├── ui/                    # UI 组件
│   │   ├── tray_icon.py       # 系统托盘图标
│   │   ├── usage_popup.py     # 用量弹出窗口
│   │   ├── provider_card.py   # 单个提供商卡片组件
│   │   └── settings_window.py # 设置窗口
│   └── utils/
│       └── curl_parser.py     # curl 命令解析 (百度认证用)
```

## 支持的 AI 提供商

| 提供商 | 认证方式 | 说明 |
|--------|---------|------|
| 智谱 (Z.ai) | API Key | BigModel 编程套餐 |
| MiniMax | API Key | MiniMax AI 服务 |
| Kimi (月之暗面) | API Key | Moonshot AI 服务 |
| 阿里云百炼 | API Key | 阿里云千帆平台 |
| OpenRouter | API Key | OpenRouter API 聚合 |
| 百度千帆 | Cookie | 百度千帆 (需 curl 解析) |
| 自定义 | API Key / Header | 通用 HTTP API 支持 |

## 核心功能

1. **系统托盘运行** - 后台常驻，托盘图标颜色反映用量状态
2. **实时用量监控** - 定时刷新（默认 60 秒），异步获取各提供商数据
3. **双模式显示** - 展开模式（卡片）和紧凑模式（行式），双击切换
4. **可拖拽窗口** - 弹出窗口支持自由拖动
5. **设置管理** - GUI 界面配置各提供商 API Key 和参数

## 应用架构

```
GlmBarApp (主控制器)
  ├── Qt Application (事件循环)
  ├── TrayIcon (系统托盘)
  │   ├── 左键点击 → 切换弹出窗口
  │   ├── 右键点击 → 上下文菜单
  │   └── 双击右键 → 切换紧凑/展开模式
  ├── UsagePopup (弹出窗口)
  │   └── ProviderCard[] (提供商卡片列表)
  ├── SettingsWindow (设置窗口)
  ├── RefreshWorker (QThread)
  │   └── ProviderRegistry.fetch_all() → UsageData[]
  └── QTimer (定时刷新)
```

## 数据流

```
QTimer 触发 → RefreshWorker (QThread)
  → 各 Provider.fetch_usage() (async)
  → 返回 UsageData (状态 + 配额信息)
  → Qt Signal 传递到主线程
  → UI 更新 (弹出窗口 + 托盘提示)
```

## 配置存储

- 位置：`~/.glmbar/config.json`
- 格式：JSON
- 首次运行自动创建默认提供商配置

## 运行方式

```bash
# 使用 uv 运行
uv run main.py

# 或安装后使用
uv pip install -e .
glmbar
```

## 优点

- 开发效率高，Python 生态丰富
- PySide6 提供原生外观
- 异步 HTTP 请求 (httpx)
- 强类型数据验证 (pydantic)
- 代码结构清晰，易于扩展

## 缺点

- 打包体积较大（PySide6 依赖）
- 启动速度相对较慢
- 需要安装 Python 运行时
- 内存占用较高
