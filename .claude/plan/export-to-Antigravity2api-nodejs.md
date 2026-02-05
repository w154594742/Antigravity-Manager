# 任务计划：创建 export-to-Antigravity2api-nodejs.py 脚本

## 上下文

**目标**：在 Antigravity-Manager 项目的 scripts 目录下创建导出脚本，将凭证导出为 Antigravity2api-node-js 项目所需的格式。

**源数据**：`~/.antigravity_tools/accounts/` 目录下的账号数据

**目标格式**：单文件 JSON 数组（`accounts.json`），每个账号包含：
- `access_token`: 访问令牌
- `refresh_token`: 刷新令牌
- `expires_in`: 有效期（秒）
- `timestamp`: 令牌获取时间（Unix 毫秒）
- `email`: 用户邮箱
- `projectId`: 项目 ID（驼峰命名）
- `enable`: 是否启用

## 执行步骤

### 步骤 1：创建导出脚本
- 文件：`scripts/export-to-Antigravity2api-nodejs.py`
- 参考现有脚本结构
- 支持范围索引参数 `--start` / `--end`
- 输出单文件 JSON 数组

### 步骤 2：更新文档
- 文件：`scripts/README.md`
- 新增第 4 节描述新脚本

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--output` | 输出文件路径 |
| `--start` | 起始索引（包含） |
| `--end` | 结束索引（包含） |
| `--include-invalid` | 包含无效账号 |
| `--dry-run` | 试运行模式 |
| `--verbose` | 详细输出 |
| `--list` | 仅列出账号 |

## 创建时间
2026-01-20
