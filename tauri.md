# GlmBar Tauri 版本

## 项目概述

GlmBar 是一个系统托盘桌面应用，用于监控多个 AI 编程套餐的用量额度。Tauri 版本基于 **Tauri v2** 重写，前端使用原生 HTML/CSS/JS，后端使用 Rust。

## 技术栈

| 组件 | 技术 |
|------|------|
| 桌面框架 | Tauri v2 |
| 后端语言 | Rust |
| 前端 | HTML5 + CSS3 + Vanilla JS (ES6) |
| HTTP 客户端 | reqwest (Rust, 异步) |
| 序列化 | serde / serde_json |
| 异步运行时 | tokio |
| 托盘图标渲染 | tiny-skia |
| 包管理 | npm + Cargo |

## 项目结构

```
tauri-app/
├── package.json                   # Node.js 项目配置
├── src/                           # 前端代码
│   ├── index.html                 # 主弹出窗口
│   ├── settings.html              # 设置窗口
│   ├── css/
│   │   ├── theme.css              # 共享暗色主题 (CSS 变量)
│   │   ├── popup.css              # 弹出窗口样式
│   │   └── settings.css           # 设置窗口样式
│   └── js/
│       ├── api.js                 # Tauri IPC 封装层
│       ├── popup.js               # 弹出窗口逻辑
│       └── settings.js            # 设置窗口逻辑
└── src-tauri/                     # Rust 后端
    ├── Cargo.toml                 # Rust 依赖配置
    ├── tauri.conf.json            # Tauri 应用配置
    ├── build.rs                   # 构建脚本
    ├── capabilities/              # 安全能力配置
    └── src/
        ├── main.rs                # 应用入口 (窗口创建 + 托盘 + 定时器)
        ├── lib.rs                 # 模块导出
        ├── commands.rs            # Tauri 命令处理器 (IPC)
        ├── tray.rs                # 系统托盘图标管理
        ├── curl_parser.rs         # curl 命令解析 (百度认证)
        ├── config/                # 配置管理
        │   ├── mod.rs             # 配置模块
        │   ├── models.rs          # 配置数据模型 (Serde)
        │   └── store.rs           # 配置持久化
        └── providers/             # AI 服务提供商
            ├── mod.rs             # Provider trait + 工厂方法
            ├── models.rs          # UsageData 数据模型
            ├── zai.rs             # 智谱 (Z.ai)
            ├── minimax.rs         # MiniMax
            ├── kimi.rs            # Kimi (月之暗面)
            ├── alibaba.rs         # 阿里云百炼
            ├── openrouter.rs      # OpenRouter
            ├── baidu.rs           # 百度千帆 (Cookie 认证)
            └── custom.rs          # 自定义 HTTP API
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

1. **系统托盘运行** - 后台常驻，托盘图标用彩色圆弧显示用量百分比
2. **实时用量监控** - 定时刷新（默认 60 秒），异步并发获取各提供商数据
3. **双模式显示** - 展开模式（卡片）和紧凑模式（行式），双击切换
4. **暗色主题** - 统一的深色 UI，CSS 变量驱动
5. **设置管理** - 独立设置窗口，管理 API Key、刷新间隔等

## 窗口配置

| 窗口 | 尺寸 | 特性 |
|------|------|------|
| Popup (弹出) | 420×400 | 透明背景、置顶、无边框、自动定位右上角 |
| Settings (设置) | 560×520 | 标准窗口、独立页面 |

## 应用架构

```
Tauri Application
  ├── Rust 后端
  │   ├── main.rs (入口)
  │   │   ├── 创建系统托盘 (tiny-skia 渲染图标)
  │   │   ├── 注册 Tauri Commands
  │   │   ├── 启动后台刷新定时器 (tokio::spawn)
  │   │   └── 管理窗口显示/隐藏
  │   ├── commands.rs (IPC 命令)
  │   │   ├── get_config
  │   │   ├── save_config
  │   │   ├── fetch_all_usage
  │   │   ├── parse_curl_command
  │   │   ├── get_available_provider_types
  │   │   ├── get_provider_fields
  │   │   └── show_settings_window
  │   ├── providers/ (Provider trait 实现)
  │   │   └── 各提供商独立实现 fetch_usage()
  │   └── config/ (配置读写)
  │       └── JSON 文件持久化
  └── 前端 (HTML/CSS/JS)
      ├── popup.js (弹出窗口交互)
      │   ├── 监听 usage-updated 事件
      │   ├── 渲染提供商卡片/行
      │   ├── 模式切换
      │   └── 窗口拖拽
      ├── settings.js (设置管理)
      │   ├── 提供商增删改
      │   ├── API Key 配置
      │   └── 刷新间隔设置
      └── api.js (Tauri IPC 封装)
```

## 数据流

```
tokio 定时器触发 → 并发调用各 Provider.fetch_usage()
  → 返回 UsageData (状态 + 配额 + 百分比)
  → 更新托盘图标 (tiny-skia 绘制彩色圆弧)
  → 发送 usage-updated 事件到前端
  → 前端 JS 重新渲染 UI
```

## 配置存储

- 位置：应用数据目录下的 JSON 文件
- 格式：JSON (通过 serde 序列化)
- 首次运行自动创建默认配置

## 运行与构建

```bash
# 开发模式
cd tauri-app
npm install
npm run tauri dev

# 生产构建
npm run tauri build
```

## 优点

- 极小的打包体积（约 5-10MB vs Python 版 100MB+）
- 极快的启动速度
- 低内存占用
- 无需安装额外运行时
- Rust 后端性能优异，并发安全
- 原生系统托盘支持
- 跨平台 (Windows / macOS / Linux)

## 缺点

- Rust 学习曲线较陡
- 前端无框架，复杂 UI 维护成本较高
- 编译时间较长
- 调试相对 Python 版不够便捷
