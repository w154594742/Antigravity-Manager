# 任务：创建 export-to-aiclient2api.py 脚本

## 上下文
参照 `scripts/export-to-gcli2api.py` 脚本，创建导出为 AIClient-2-API 项目可用的 antigravity 授权文件。

## 目标格式
- 文件命名：`{timestamp}_antigravity_{email_underscored}.json`
- JSON 内容：与 gcli2api 格式相同

## 执行步骤

1. [x] 创建脚本文件框架
2. [x] 实现数据读取模块
3. [x] 实现账号验证模块
4. [x] 实现数据转换模块
5. [x] 实现文件命名模块（核心差异）
6. [x] 实现文件导出模块
7. [x] 实现报告输出模块
8. [x] 实现主流程

## 关键差异
| 模块 | gcli2api | aiclient2api |
|------|----------|--------------|
| 文件命名 | `antigravity_{email}.json` | `{timestamp}_antigravity_{email_underscored}.json` |
| 默认目录 | `~/Downloads/gcli2api` | `~/Downloads/aiclient2api` |
