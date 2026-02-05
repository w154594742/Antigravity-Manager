# CLAUDE.md

[根目录](../CLAUDE.md) > **src-tauri**

## 模块职责
后端核心层，基于 Rust 开发，负责核心业务逻辑、本地数据库、外部进程管理及 API 反代服务器。

## 入口与启动
- **二进制入口**: `src-tauri/src/main.rs`
- **Tauri 配置**: `src-tauri/src/lib.rs` (注册命令、插件、托盘)

## 对外接口 (Tauri Commands)
定义在 `src-tauri/src/commands/`：
- `mod.rs`: 通用账号与配置命令
- `proxy.rs`: 反代服务控制命令
- `network_proxy.rs`: 网络代理设置

## 核心组件
1. **API 反代 (proxy/)**:
   - 使用 Axum 启动 HTTP 服务
   - `converter.rs`: 协议转换逻辑 (OpenAI/Anthropic -> Gemini)
   - `token_manager.rs`: 账号轮询与负载均衡
2. **进程管理 (modules/process.rs)**: 管理外部 Antigravity CLI 进程
3. **数据持久化 (modules/db.rs)**: SQLite 数据库操作
4. **系统托盘 (modules/tray.rs)**: 托盘菜单与交互

## 关键依赖
- `tauri`: 桌面框架
- `axum`: Web 服务器框架
- `rusqlite`: SQLite 驱动
- `reqwest`: HTTP 客户端
- `tokio`: 异步运行时

## 数据模型
定义在 `src-tauri/src/models/`：
- `account.rs`: 账号信息
- `token.rs`: Token 数据
- `config.rs`: 应用配置

## 测试与质量
- 运行 `cargo test` 执行单元测试。
- 使用 `cargo clippy` 进行静态代码分析。

## 变更记录 (Changelog)
- 2026-02-04: 初始化模块文档。
