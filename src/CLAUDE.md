# CLAUDE.md

[根目录](./CLAUDE.md) > **src**

## 模块职责
前端展示层，基于 React 19 开发，负责用户界面展示、状态管理以及与 Rust 后端的 IPC 通信。

## 入口与启动
- **入口文件**: `src/main.tsx`
- **根组件**: `src/App.tsx` (配置 React Router v7 路由)

## 对外接口 (与 Tauri 通信)
使用 `@tauri-apps/api/core` 的 `invoke` 调用后端命令。主要服务封装在 `src/services/`：
- `accountService.ts`: 账号增删改查
- `configService.ts`: 应用配置管理

## 关键依赖与配置
- **状态管理**: `Zustand` (`src/stores/`)
- **样式**: `TailwindCSS` + `DaisyUI`
- **国际化**: `i18next` (`src/locales/`)
- **图表**: `Recharts`

## 目录结构
- `pages/`: 页面组件 (Dashboard, Accounts, ApiProxy, Settings)
- `components/`: UI 组件，按功能模块划分子目录
- `stores/`: 全局状态定义
- `types/`: TypeScript 类型定义
- `utils/`: 格式化等工具函数

## 测试与质量
- 使用 `npx tsc --noEmit` 进行类型检查。

## 相关文件清单
- `package.json`: 前端依赖与脚本
- `vite.config.ts`: 构建配置
- `tailwind.config.js`: 样式配置

## 变更记录 (Changelog)
- 2026-02-04: 初始化模块文档。
