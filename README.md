# GlmBar

一款轻量级的 Windows 系统托盘应用，用于实时监控多个 AI 编程套餐的使用量。

[![license](https://img.shields.io/badge/license-MIT-blue.svg)](#许可证)

## 快速开始

启动应用后，程序会在系统托盘（右下角隐藏图标区域）中运行，不会显示主窗口。

### 基本操作

| 操作 | 说明 |
|------|------|
| **左键单击** 托盘图标 | 弹出用量详情面板，显示各服务商的使用量 |
| **右键单击** 托盘图标 | 打开菜单，可刷新数据或进入设置 |
| **右键双击** 弹出面板 | 在简洁面板和详细面板之间切换 |

### 首次使用

1. 右键点击托盘图标 → **设置**
2. 点击 **添加服务商**，选择服务商类型
3. 填写 API 密钥（智谱、MiniMax 等）或粘贴 cURL 命令（百度千帆、OpenCode）
4. 保存后左键点击图标即可查看用量

## 功能特性

- **系统托盘监控** - 托盘图标动态显示用量百分比，鼠标悬停查看详细信息
- **多服务商支持** - 支持智谱AI、MiniMax、Kimi、阿里云百炼、OpenRouter、百度千帆、OpenCode Go 等主流 AI 服务商
- **自定义服务商** - 支持添加任意兼容 OpenAI 格式的 API 服务商
- **自动刷新** - 可配置刷新间隔，后台自动获取最新用量
- **轻量高效** - Python 版基于 PySide6，Tauri 版安装包仅约 5MB
- **双端实现** - 同一功能提供 Python (PySide6) 与 Tauri (Rust) 两套实现，可按需选择

## 支持的服务商

| 服务商 | 配置方式 | 备注 |
|--------|----------|------|
| 智谱AI (GLM) | API Key + 区域 | 支持国内/国际版 |
| MiniMax | API Key + 区域 | 支持国内/国际版 |
| Kimi (月之暗面) | API Key | - |
| 阿里云百炼 | API Key + 区域 | 支持国内/国际版 |
| OpenRouter | API Key | - |
| 百度千帆 | cURL 命令 | 从控制台复制 |
| OpenCode Go | cURL 命令 | 从 opencode.ai 复制；海外站点，Tauri 版自动走系统代理 |
| 自定义 | API Key + 配额URL | 兼容 OpenAI 格式 |

## 安装

从 [Releases](https://github.com/wkc1235466/glmBar/releases) 页面下载最新的安装包。

> Tauri 版提供 Windows 安装包（`.exe` / `.msi`）；Python 版可直接源码运行。

## 截图

### 托盘图标
托盘图标会根据用量百分比动态变化，直观显示当前使用情况。

### 弹出面板
点击托盘图标显示详细用量信息，包含各服务商的已用额度、剩余额度和使用百分比。

### 设置界面
右键托盘图标 → 设置，可以添加、编辑、删除服务商配置。

## 开发

项目提供两个版本：Python 版本（PySide6 桌面应用）和 Tauri 版本（Rust 后端），两者功能对等。

### Python 版本

#### 环境要求

- Python 3.11+

#### 本地运行

```bash
# 安装依赖
uv sync

# 运行应用
python main.py
```

#### 技术栈

- **GUI 框架**: PySide6
- **网络请求**: httpx (异步 HTTP)
- **配置管理**: Pydantic
- **数据模型**: dataclass

#### 项目结构

```
glmBar/
├── main.py                   # 应用入口
├── src/
│   ├── config/
│   │   └── settings.py       # 配置管理 (AppConfig, ProviderConfig)
│   ├── providers/
│   │   ├── base.py           # BaseProvider 基类与数据模型
│   │   ├── registry.py       # Provider 注册表与 CustomProvider
│   │   ├── zai.py            # 智谱AI
│   │   ├── minimax.py        # MiniMax
│   │   ├── kimi.py           # Kimi
│   │   ├── alibaba.py        # 阿里云百炼
│   │   ├── openrouter.py     # OpenRouter
│   │   ├── baidu.py          # 百度千帆 (Cookie 认证)
│   │   └── opencode.py       # OpenCode Go (Cookie 认证)
│   ├── ui/
│   │   ├── tray.py           # 系统托盘图标与弹出面板
│   │   └── settings.py       # 设置界面
│   └── utils/
│       └── curl_parser.py    # cURL 命令解析
├── pyproject.toml
└── README.md
```

### Tauri 版本

#### 环境要求

- Node.js 18+
- Rust 1.70+
- pnpm/npm

#### 本地运行

```bash
cd tauri-app

# 安装依赖
npm install

# 开发模式
npm run dev

# 构建发布版本
npm run build
```

构建产物位于 `src-tauri/target/release/bundle/` 目录。

#### 技术栈

- **前端**: 原生 HTML/CSS/JavaScript（无框架）
- **后端**: Rust + Tauri v2
- **网络**: reqwest (异步 HTTP 客户端)
- **图标渲染**: tiny-skia (软件渲染)

## 参考项目

本项目在设计与实现上参考了以下项目，特此致谢：

- [CodexBar](https://github.com/steipete/CodexBar) — AI 编程套餐用量监控的托盘应用，本项目的整体形态与多项服务商适配思路受其启发。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
