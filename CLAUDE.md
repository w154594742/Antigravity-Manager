# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Antigravity Tools 是一个基于 Tauri v2 开发的桌面应用程序，提供 Gemini 和 Claude AI 账号管理以及本地 API 反代服务。

**核心功能：**
- 账号管理：管理多个 Google/Anthropic 账号，自动刷新 Token，监控配额
- API 反代服务：内置 Rust 高性能反代服务器，将 Web Session 转化为 OpenAI/Anthropic API 接口
- 智能轮询：自动账号负载均衡、故障转移、配额感知
- 多协议支持：兼容 OpenAI (`/v1/chat/completions`) 和 Anthropic (`/v1/messages`) 协议

## 技术栈

**前端：**
- React 19 + TypeScript
- React Router v7 (路由管理)
- Zustand (状态管理)
- TailwindCSS + DaisyUI (UI 框架)
- i18next (国际化)
- Recharts (图表)

**后端：**
- Tauri v2 (桌面框架)
- Rust (核心业务逻辑)
- Axum (反代服务器)
- SQLite/Rusqlite (本地数据存储)
- Reqwest (HTTP 客户端)

## 开发命令

### 前端开发
```bash
# 安装依赖
npm install

# 启动开发服务器（仅前端，无 Tauri）
npm run dev

# TypeScript 类型检查
npx tsc --noEmit

# 构建前端资源
npm run build
```

### Tauri 开发
```bash
# 启动 Tauri 开发模式（前端 + Rust 后端）
npm run tauri dev

# 构建生产版本
npm run tauri build

# 构建 macOS Universal 二进制（Intel + Apple Silicon）
npm run build:universal
```

### Rust 后端
```bash
# 进入 Rust 目录
cd src-tauri

# 检查 Rust 代码
cargo check

# 运行测试
cargo test

# 格式化代码
cargo fmt

# Clippy 静态分析
cargo clippy
```

## 代码架构

### 前端架构 (`src/`)

```
src/
├── App.tsx                    # 根组件，路由配置
├── main.tsx                   # 应用入口
├── pages/                     # 页面组件
│   ├── Dashboard.tsx          # 仪表盘页面
│   ├── Accounts.tsx           # 账号管理页面
│   ├── ApiProxy.tsx           # API 反代配置页面
│   └── Settings.tsx           # 设置页面
├── components/                # 可复用组件
│   ├── accounts/              # 账号相关组件
│   ├── dashboard/             # 仪表盘组件
│   ├── common/                # 通用组件（Toast、Modal、Theme 等）
│   └── layout/                # 布局组件（Layout、Navbar）
├── stores/                    # Zustand 状态管理
│   ├── useAccountStore.ts     # 账号状态管理
│   └── useConfigStore.ts      # 配置状态管理
└── locales/                   # i18n 国际化资源
    ├── zh.json
    └── en.json
```

**状态管理模式：**
- 使用 Zustand 管理全局状态（账号列表、应用配置）
- 通过 Tauri IPC 与 Rust 后端通信 (`@tauri-apps/api/core`)
- 事件监听机制：使用 `@tauri-apps/api/event` 监听托盘菜单事件

### 后端架构 (`src-tauri/src/`)

```
src-tauri/src/
├── lib.rs                     # Tauri 应用入口，注册命令和插件
├── main.rs                    # 二进制入口
├── models/                    # 数据模型
│   ├── account.rs             # 账号数据结构
│   ├── token.rs               # Token 数据结构
│   ├── quota.rs               # 配额数据结构
│   └── config.rs              # 配置数据结构
├── modules/                   # 业务模块
│   ├── account.rs             # 账号管理逻辑
│   ├── quota.rs               # 配额查询逻辑
│   ├── config.rs              # 配置管理
│   ├── db.rs                  # SQLite 数据库操作
│   ├── process.rs             # 外部进程管理（Antigravity CLI）
│   ├── oauth.rs               # OAuth 登录流程
│   ├── oauth_server.rs        # OAuth 回调服务器
│   ├── tray.rs                # 系统托盘管理
│   └── logger.rs              # 日志系统
├── proxy/                     # API 反代服务（核心功能）
│   ├── server.rs              # Axum HTTP 服务器
│   ├── client.rs              # Gemini/Claude API 客户端
│   ├── converter.rs           # OpenAI ↔ Gemini 协议转换
│   ├── token_manager.rs       # 账号轮询与故障转移
│   ├── project_resolver.rs    # Gemini Project ID 解析
│   └── config.rs              # 反代服务配置
├── commands/                  # Tauri 命令处理器
│   ├── mod.rs                 # 账号/配额/配置命令
│   └── proxy.rs               # 反代服务命令
└── utils/                     # 工具函数
    └── protobuf.rs            # Protobuf 解析工具
```

**关键模块说明：**

1. **proxy 模块（API 反代核心）：**
   - `server.rs`: 启动 Axum 服务器，处理 `/v1/chat/completions` 和 `/v1/messages` 请求
   - `converter.rs`: 将 OpenAI/Anthropic 格式转换为 Gemini 内部格式
   - `token_manager.rs`: 实现智能轮询、自动重试、故障转移逻辑
   - `client.rs`: 封装与 Gemini/Claude API 的 HTTP 通信

2. **modules/process.rs：**
   - 管理外部 Antigravity CLI 进程的启动/停止
   - 实现账号切换时的进程控制（精确 PID 管理 + SIGTERM/SIGKILL）

3. **modules/tray.rs：**
   - 系统托盘菜单创建与更新
   - 快速账号切换、配额查看、服务控制

4. **modules/db.rs：**
   - SQLite 数据库初始化与迁移
   - 账号数据 CRUD 操作

## 重要约定

### 数据库
- 使用 SQLite，数据库路径由 `dirs::data_local_dir()` 动态确定
- 账号数据表：存储账号信息、Token、配额数据
- 数据迁移通过 `modules/migration.rs` 管理版本

### 外部依赖
- 依赖外部 Antigravity CLI 工具（需在系统 PATH 中）
- 通过 `modules/process.rs` 调用 CLI 实现账号切换等功能

### 跨平台差异
- macOS: 使用 `ActivationPolicy` 控制应用在 Dock 显示/隐藏
- Linux: 部分构建需要特定依赖（参考 Ubuntu 构建错误修复提交）
- Windows: 使用 `windows_subsystem = "windows"` 隐藏控制台

### API 协议转换
- OpenAI → Gemini: `converter::convert_openai_to_gemini()`
- Anthropic → Gemini: `converter::convert_anthropic_to_gemini()`
- 支持流式 SSE 响应，兼容多轮对话上下文

### 图片生成
- 使用 Gemini Imagen 3 模型
- 支持多种尺寸：`1:1`, `16:9`, `9:16`, `4:3`, `4K`
- 通过模型后缀（如 `gemini-3-pro-image-16x9`）或 API 参数（`size`, `quality`）控制

## 常见任务

### 添加新的 Tauri 命令
1. 在 `src-tauri/src/commands/` 中定义命令函数（使用 `#[tauri::command]` 宏）
2. 在 `lib.rs` 的 `invoke_handler` 中注册命令
3. 在前端通过 `@tauri-apps/api/core` 的 `invoke()` 调用

### 修改反代服务端点
1. 编辑 `src-tauri/src/proxy/server.rs` 的路由定义
2. 如需协议转换，修改 `converter.rs` 中的转换函数
3. 重新编译 Rust 后端（`npm run tauri dev` 会自动重编译）

### 更新国际化文案
1. 修改 `src/locales/zh.json` 或 `en.json`
2. 在组件中使用 `useTranslation` hook 引用翻译键

### 调试 Rust 代码
- 使用 `tracing` 日志库（`tracing::info!`, `tracing::error!` 等）
- 开发模式下日志会输出到终端
- 生产版本日志保存到应用数据目录

## 版本发布流程

1. 更新版本号：
   - `package.json` 中的 `version`
   - `src-tauri/Cargo.toml` 中的 `version`
   - `src-tauri/tauri.conf.json` 中的 `version`

2. 更新 `README.md` 中的版本号和 CHANGELOG

3. 构建发布版本：
   ```bash
   # macOS Universal Binary
   npm run build:universal

   # Linux/Windows
   npm run tauri build
   ```

4. GitHub Release 由 `.github/workflows/release.yml` 自动处理

## 注意事项

- **严格遵循 SOLID、KISS、DRY、YAGNI 原则**
- 代码注释使用中文，确保清晰描述关键逻辑
- 新功能应在 README 中同步更新文档
- 涉及 Token/账号等敏感数据时，确保不记录到日志
- macOS 15.x 进程管理已优化，避免修改 `process.rs` 中的超时和信号逻辑
