# Scripts 使用文档

本目录包含 Antigravity Manager 项目的凭证导出脚本，支持导出到四个不同的目标项目。

## 脚本概览

| 脚本文件 | 目标项目 | 默认输出 | 输出格式特征 |
|---------|---------|----------|-------------|
| `export-to-Antigravity2Api.py` | Antigravity2Api | `~/Downloads/Antigravity2Api/` | 多文件，`expiry_date` Unix毫秒 |
| `export-to-Antigravity2api-nodejs.py` | Antigravity2api-nodejs | `~/Downloads/.../accounts.json` | **单文件数组**，`timestamp` + `expires_in` |
| `export-to-cliproxyapi.py` | CLIProxyAPI | `~/Downloads/cliproxyapi/` | 多文件，`type: "antigravity"` |
| `export-to-gcli2api.py` | gcli2api | `~/Downloads/gcli2api/` | 多文件，含 `client_id`、`scopes` 数组 |

---

## 1. 导出到 Antigravity2Api

**文件**: `export-to-Antigravity2Api.py`

**目标项目**: [Antigravity2Api](https://github.com/user/Antigravity2Api)

**使用方法**:
```bash
# 导出有效账号到默认目录 ~/Downloads/Antigravity2Api
python3 scripts/export-to-Antigravity2Api.py

# 自定义输出目录
python3 scripts/export-to-Antigravity2Api.py --output-dir ~/Desktop/custom

# 包含无效账号
python3 scripts/export-to-Antigravity2Api.py --include-invalid

# 试运行（不写入文件）
python3 scripts/export-to-Antigravity2Api.py --dry-run

# 详细输出
python3 scripts/export-to-Antigravity2Api.py --verbose
```

**输出格式**:
```json
{
  "access_token": "ya29.a0AfH6SMB...",
  "refresh_token": "1//0gx...",
  "expiry_date": 1704067200000,
  "expires_in": 3599,
  "token_type": "Bearer",
  "scope": "https://www.googleapis.com/auth/cloud-platform ...",
  "email": "user@gmail.com",
  "projectId": "my-project-12345"
}
```

**文件命名**: `{email_with_underscores}.json`
- 例如: `user_gmail_com.json`

**导入方式**:
1. 将导出的 JSON 文件复制到 Antigravity2Api 的 `auths/` 目录
2. 重启服务或调用 `/admin/api/accounts/reload` 接口

---

## 2. 导出到 Antigravity2api-nodejs（单文件数组）

**文件**: `export-to-Antigravity2api-nodejs.py`

**目标项目**: [Antigravity2api-nodejs](https://github.com/user/Antigravity2api-nodejs)

**特点**:
- 输出单个 `accounts.json` 文件（JSON 数组）
- **默认交互式选择**：直接运行会显示账号列表，让你选择导出范围
- 支持连续范围、离散选择、混合模式

**使用方法**:
```bash
# 交互式选择账号（默认）
python3 scripts/export-to-Antigravity2api-nodejs.py

# 非交互模式：导出全部账号
python3 scripts/export-to-Antigravity2api-nodejs.py -n

# 非交互模式：导出索引 0-9 的账号
python3 scripts/export-to-Antigravity2api-nodejs.py --start 0 --end 9

# 列出所有账号及其索引（不导出）
python3 scripts/export-to-Antigravity2api-nodejs.py --list

# 自定义输出文件路径
python3 scripts/export-to-Antigravity2api-nodejs.py --output ~/Desktop/accounts.json

# 试运行（不写入文件）
python3 scripts/export-to-Antigravity2api-nodejs.py --dry-run

# 包含无效账号
python3 scripts/export-to-Antigravity2api-nodejs.py --include-invalid
```

**交互模式示例**:
```
======================================================================
  Antigravity Manager → Antigravity2api-nodejs 凭证导出工具
======================================================================

📂 数据目录: ~/.antigravity_tools
✓ 找到 25 个账号

----------------------------------------------------------------------
索引    邮箱                                状态
----------------------------------------------------------------------
0       user1@gmail.com                     ✓ 有效
1       user2@gmail.com                     ✓ 有效
2       user3@gmail.com                     ✗ Token 已过期
...
----------------------------------------------------------------------

请输入要导出的账号范围:
  - 连续范围: 0-9
  - 单个索引: 0,3,5,8
  - 混合模式: 0-5,8,10-12
  - 全部导出: all 或直接回车
  - 取消: q

> 0-9

确认导出这 10 个账号？[Y/n] y
```

**输出格式**（单文件 JSON 数组）:
```json
[
  {
    "access_token": "ya29.a0AfH6SMB...",
    "refresh_token": "1//0gx...",
    "expires_in": 3599,
    "timestamp": 1704063601000,
    "email": "user@gmail.com",
    "projectId": "my-project-12345",
    "enable": true
  }
]
```

**专用参数**:

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-n, --no-interactive` | 禁用交互模式（用于脚本自动化） | 交互模式 |
| `--start` | 起始账号索引（自动切换非交互模式） | 0 |
| `--end` | 结束账号索引（自动切换非交互模式） | 末尾 |
| `--list` | 仅列出账号索引（不导出） | - |

**导入方式**:
1. 将导出的 `accounts.json` 复制到 Antigravity2api-nodejs 的 `data/` 目录
2. 重启 Antigravity2api-nodejs 服务
3. 访问管理界面确认账号已加载

---

## 3. 导出到 CLIProxyAPI

**文件**: `export-to-cliproxyapi.py`

**目标项目**: [CLIProxyAPI](https://github.com/user/CLIProxyAPI)

**使用方法**:
```bash
# 导出有效账号到默认目录 ~/Downloads/cliproxyapi
python3 scripts/export-to-cliproxyapi.py

# 指定输出目录
python3 scripts/export-to-cliproxyapi.py --output ~/Desktop/custom

# 仅导出指定邮箱的账号
python3 scripts/export-to-cliproxyapi.py --email user@gmail.com

# 包含无效账号
python3 scripts/export-to-cliproxyapi.py --include-invalid
```

**输出格式**:
```json
{
  "access_token": "...",
  "email": "user@gmail.com",
  "expired": "2026-01-16T15:30:45+08:00",
  "expires_in": 3600,
  "project_id": "...",
  "refresh_token": "...",
  "timestamp": 1737011445000,
  "type": "antigravity"
}
```

**文件命名**: `antigravity-{email_with_underscores}.json`
- 例如: `antigravity-user_gmail_com.json`

---

## 4. 导出到 gcli2api

**文件**: `export-to-gcli2api.py`

**目标项目**: [gcli2api](https://github.com/user/gcli2api)

**使用方法**:
```bash
# 导出有效账号到默认目录 ~/Downloads/gcli2api
python3 scripts/export-to-gcli2api.py

# 自定义输出目录
python3 scripts/export-to-gcli2api.py --output-dir ~/Desktop/custom

# 包含无效账号
python3 scripts/export-to-gcli2api.py --include-invalid

# 试运行
python3 scripts/export-to-gcli2api.py --dry-run

# 详细输出
python3 scripts/export-to-gcli2api.py --verbose
```

**输出格式**:
```json
{
  "client_id": "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com",
  "client_secret": "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",
  "token": "ya29.a0AfH6SMB...",
  "refresh_token": "1//0gx...",
  "scopes": [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs"
  ],
  "token_uri": "https://oauth2.googleapis.com/token",
  "project_id": "...",
  "expiry": "2026-01-17T02:30:45+00:00"
}
```

**文件命名**: `antigravity_{email}.json`
- 例如: `antigravity_user@gmail.com.json`

**导入方式**:
1. 打开 gcli2api Web 界面: `http://127.0.0.1:7861/auth`
2. 进入「批量上传」标签页
3. 在 Antigravity 凭证区域上传导出的 JSON 文件

---

## 通用参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--output` / `--output-dir` | 指定输出目录 | `~/Downloads/{项目类型}` |
| `--email` | 仅导出指定邮箱的账号 | 导出全部 |
| `--include-invalid` | 包含无效账号 | 仅导出有效账号 |
| `--dry-run` | 试运行（不写入文件） | 正常写入 |
| `--verbose` | 显示详细输出 | 简洁输出 |

---

## 数据源

**源目录**: `~/.antigravity_tools/accounts/`

所有脚本从该目录读取账号数据，提取凭证信息并转换为目标格式。

---

## 账号验证逻辑

所有脚本默认跳过以下账号（可通过 `--include-invalid` 参数包含）：

- 已禁用的账号 (`disabled: true`)
- 缺少 `access_token` 或 `refresh_token` 的账号
- Token 已过期的账号（预留 5 分钟缓冲）
- 被 403 禁止访问的账号 (`quota.is_forbidden: true`)

---

## 输出格式对比

| 字段 | Antigravity2Api | Antigravity2api-nodejs | CLIProxyAPI | gcli2api |
|------|-----------------|------------------------|-------------|----------|
| 访问令牌 | `access_token` | `access_token` | `access_token` | `token` |
| 刷新令牌 | `refresh_token` | `refresh_token` | `refresh_token` | `refresh_token` |
| 过期时间 | `expiry_date` (Unix毫秒) | `timestamp` + `expires_in` | `expired` (RFC3339) | `expiry` (ISO 8601) |
| 项目ID | `projectId` (驼峰) | `projectId` (驼峰) | `project_id` | `project_id` |
| 启用状态 | - | `enable` | - | - |
| 令牌类型 | `token_type: "Bearer"` | - | - | - |
| 权限范围 | `scope` (字符串) | - | - | `scopes` (数组) |
| 提供商类型 | - | - | `type: "antigravity"` | - |
| 客户端凭证 | - | - | - | `client_id`, `client_secret` |
| 输出方式 | 多文件 | **单文件数组** | 多文件 | 多文件 |

---

## 常见问题

### Q1: 源目录不存在怎么办？
**A**: 脚本会提示错误并退出。请确保：
1. 已通过 Antigravity Manager 登录过账号
2. 账号数据已保存到本地

### Q2: 为什么某些账号被跳过？
**A**: 脚本默认跳过无效账号（禁用/过期/403）。如需导出所有账号，使用 `--include-invalid` 参数。

### Q3: 如何选择使用哪个脚本？
**A**: 根据目标项目选择：
- 导入到 **Antigravity2Api** → 使用 `export-to-Antigravity2Api.py`（多文件）
- 导入到 **Antigravity2api-nodejs** → 使用 `export-to-Antigravity2api-nodejs.py`（单文件数组）
- 导入到 **CLIProxyAPI** → 使用 `export-to-cliproxyapi.py`（多文件）
- 导入到 **gcli2api** → 使用 `export-to-gcli2api.py`（多文件）

### Q4: 如何只导出部分账号？
**A**: 使用 `export-to-Antigravity2api-nodejs.py` 脚本的范围参数：
```bash
# 先列出所有账号查看索引
python3 scripts/export-to-Antigravity2api-nodejs.py --list

# 导出指定范围
python3 scripts/export-to-Antigravity2api-nodejs.py --start 0 --end 9
```

---

## 设计原则

- **SOLID**: 单一职责，每个脚本只负责一种目标格式
- **KISS**: 避免过度设计，保持简洁
- **DRY**: 抽取可复用函数（验证、转换、格式化）
- **YAGNI**: 仅实现必要功能

---

## 作者

**wangqiupei**

如有问题或建议，请提交 Issue。
