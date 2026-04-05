# GlmBar

一款轻量级的 Windows 系统托盘应用，用于实时监控多个 AI 编程套餐的使用量。

## 功能特性

- **系统托盘监控** - 托盘图标动态显示用量百分比，鼠标悬停查看详细信息
- **多服务商支持** - 支持智谱AI、MiniMax、Kimi、阿里云百炼、OpenRouter、百度千帆等主流 AI 服务商
- **自定义服务商** - 支持添加任意兼容 OpenAI 格式的 API 服务商
- **自动刷新** - 可配置刷新间隔，后台自动获取最新用量
- **轻量高效** - 基于 Tauri v2 构建，安装包仅约 5MB，内存占用极低

## 支持的服务商

| 服务商 | 配置方式 | 备注 |
|--------|----------|------|
| 智谱AI (GLM) | API Key + 区域 | 支持国内/国际版 |
| MiniMax | API Key + 区域 | 支持国内/国际版 |
| Kimi (月之暗面) | API Key | - |
| 阿里云百炼 | API Key + 区域 | 支持国内/国际版 |
| OpenRouter | API Key | - |
| 百度千帆 | cURL 命令 | 从控制台复制 |
| 自定义 | API Key + 配额URL | 兼容 OpenAI 格式 |

## 安装

从 [Releases](https://github.com/wkc1235466/glmBar/releases) 页面下载最新的安装包。

## 使用方法

1. **启动应用** - 运行后会在系统托盘显示图标
2. **查看用量** - 左键点击托盘图标弹出详细面板
3. **配置服务商** - 右键托盘图标 → 设置，添加 API 密钥
4. **刷新数据** - 右键托盘图标 → 刷新，或点击面板中的刷新按钮

## 截图

### 托盘图标
托盘图标会根据用量百分比动态变化，直观显示当前使用情况。

### 弹出面板
点击托盘图标显示详细用量信息，包含各服务商的已用额度、剩余额度和使用百分比。

### 设置界面
右键托盘图标 → 设置，可以添加、编辑、删除服务商配置。

## 开发

### 环境要求

- Node.js 18+
- Rust 1.70+
- pnpm/npm

### 本地运行

```bash
cd tauri-app

# 安装依赖
npm install

# 开发模式
npm run tauri dev

# 构建发布版本
npm run tauri build
```

构建产物位于 `src-tauri/target/release/bundle/` 目录。

## 技术栈

- **前端**: 原生 HTML/CSS/JavaScript（无框架）
- **后端**: Rust + Tauri v2
- **网络**: reqwest (异步 HTTP 客户端)
- **图标渲染**: tiny-skia (软件渲染)

## 项目结构

```
glmBar/
├── tauri-app/                # Tauri 应用目录
│   ├── src/                  # 前端源码
│   │   ├── index.html        # 弹出面板
│   │   ├── settings.html     # 设置界面
│   │   ├── css/              # 样式文件
│   │   └── js/               # JavaScript 模块
│   └── src-tauri/            # Rust 后端
│       ├── src/
│       │   ├── main.rs       # 入口文件
│       │   ├── commands.rs   # Tauri 命令
│       │   ├── tray.rs       # 托盘图标生成
│       │   ├── providers/    # 服务商实现
│       │   └── config/       # 配置管理
│       └── tauri.conf.json   # Tauri 配置
└── README.md
```

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！
