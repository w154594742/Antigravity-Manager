# Scripts 使用文档

本目录包含 Antigravity Manager 项目的实用脚本工具。

## 账号导出工具

提供两个版本的账号导出脚本,功能完全一致:

### 1. Python 版本 (推荐)

**文件**: `export-accounts.py`

**优势**:
- ✅ 零外部依赖 (使用 Python 标准库)
- ✅ 代码可读性和可维护性高
- ✅ 跨平台兼容性好
- ✅ 符合 SOLID、KISS、DRY 原则

**使用方法**:
```bash
# 导出所有有效账号到默认目录
python3 scripts/export-accounts.py

# 指定输出目录
python3 scripts/export-accounts.py --output ~/Downloads/accounts

# 仅导出指定邮箱的账号
python3 scripts/export-accounts.py --email user@gmail.com

# 包含无效账号(默认跳过禁用/过期/403账号)
python3 scripts/export-accounts.py --include-invalid

# 组合使用
python3 scripts/export-accounts.py --output ./exports --email user@gmail.com
```

**参数说明**:
- `--output <目录>`: 指定输出目录,默认为 `~/Desktop/antigravity-exports`
- `--email <邮箱>`: 仅导出指定邮箱的账号
- `--include-invalid`: 包含无效账号(默认跳过)

**验证逻辑**:
脚本会自动跳过以下账号:
- 已禁用的账号 (`disabled: true`)
- 缺少 `access_token` 或 `refresh_token` 的账号
- Token 已过期的账号(预留 5 分钟缓冲)
- 被 403 禁止访问的账号 (`quota.is_forbidden: true`)

---

### 2. Node.js 版本

**文件**: `export-accounts.mjs`

**优势**:
- ✅ 原生 ES Module 支持
- ✅ 已经过充分测试和验证
- ✅ 适合熟悉 JavaScript 的开发者

**使用方法**:
```bash
# 导出所有有效账号到默认目录
node scripts/export-accounts.mjs

# 指定输出目录
node scripts/export-accounts.mjs --output ~/Downloads/accounts

# 仅导出指定邮箱的账号
node scripts/export-accounts.mjs --email user@gmail.com

# 包含无效账号
node scripts/export-accounts.mjs --include-invalid
```

**参数说明**: (与 Python 版本相同)

---

## 输出格式

导出的账号文件遵循 Antigravity 标准格式:

**文件命名**: `antigravity-<email_with_underscores>.json`
- 例如: `antigravity-user_gmail_com.json`

**文件内容**:
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

**字段说明**:
- `access_token`: 访问令牌
- `email`: 账号邮箱
- `expired`: Token 过期时间 (ISO 8601 格式,带时区)
- `expires_in`: Token 有效期(秒)
- `project_id`: Gemini 项目 ID (可能为 null)
- `refresh_token`: 刷新令牌
- `timestamp`: 导出时间戳(毫秒)
- `type`: 固定为 "antigravity"

---

## 数据源

**源目录**: `~/.antigravity_tools/accounts/`

脚本会读取该目录下的所有 `.json` 文件,提取账号信息并转换为标准格式。

---

## 常见问题

### Q1: 源目录不存在怎么办?
**A**: 脚本会提示错误并退出。请确保:
1. 已通过 Antigravity Manager 登录过账号
2. 账号数据已保存到本地

### Q2: 为什么某些账号被跳过?
**A**: 脚本默认跳过以下账号:
- 已禁用的账号
- Token 缺失或过期的账号
- 被 403 禁止访问的账号

如需导出所有账号,使用 `--include-invalid` 参数。

### Q3: Python 版本和 Node.js 版本有什么区别?
**A**: 功能完全一致,仅实现语言不同:
- **Python 版本**: 零外部依赖,代码更简洁
- **Node.js 版本**: 适合前端开发者,已充分测试

根据个人偏好选择即可。

### Q4: 输出的 JSON 文件可以直接导入 Antigravity 吗?
**A**: 是的,输出格式符合 Antigravity 标准,可以直接使用。

---

## 技术实现对比

| 维度 | Python 版本 | Node.js 版本 |
|------|-------------|--------------|
| **依赖** | Python 标准库 | Node.js 运行时 |
| **代码行数** | ~350 行 | ~315 行 |
| **类型安全** | 类型注解 | JSDoc 注释 |
| **错误处理** | try/except | try/catch |
| **时间处理** | datetime 模块 | Date 对象 |
| **JSON 处理** | json 模块 | JSON 对象 |
| **参数解析** | argparse | 手动解析 |

---

## 开发者备注

**设计原则**:
- ✅ **SOLID**: 单一职责,函数解耦
- ✅ **KISS**: 避免过度设计,保持简洁
- ✅ **DRY**: 抽取可复用函数 (验证、转换、格式化)
- ✅ **YAGNI**: 仅实现必要功能,不预留未来特性

**代码质量**:
- 详细的中文注释
- 完整的错误处理
- 清晰的类型标注 (Python) / JSDoc (Node.js)
- 统一的代码风格

---

## 作者

**wangqiupei**

如有问题或建议,请提交 Issue。
