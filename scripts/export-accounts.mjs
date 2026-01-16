#!/usr/bin/env node
/**
 * 账号数据导出脚本
 * 将项目内账号格式转换为 Antigravity 标准格式
 *
 * 使用方法:
 *   node scripts/export-accounts.mjs [--output <目录>] [--email <邮箱>] [--include-invalid]
 *
 * 参数说明:
 *   --output <目录>    指定输出目录，默认为 ~/Desktop/antigravity-exports
 *   --email <邮箱>     仅导出指定邮箱的账号
 *   --include-invalid  包含无效账号（默认跳过禁用/过期/403账号）
 *
 * @author wangqiupei
 */

import fs from 'fs';
import path from 'path';
import os from 'os';

// 源数据目录
const SOURCE_DIR = path.join(os.homedir(), '.antigravity_tools', 'accounts');
// 默认输出目录
const DEFAULT_OUTPUT_DIR = path.join(os.homedir(), 'Desktop', 'antigravity-exports');

/**
 * 解析命令行参数
 */
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    output: DEFAULT_OUTPUT_DIR,
    email: null,
    includeInvalid: false  // 是否包含无效账号
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--output' && args[i + 1]) {
      options.output = args[++i];
    } else if (args[i] === '--email' && args[i + 1]) {
      options.email = args[++i];
    } else if (args[i] === '--include-invalid') {
      options.includeInvalid = true;
    }
  }

  return options;
}

/**
 * 验证账号有效性
 * 返回 { valid: boolean, reason: string }
 */
function validateAccount(account) {
  const { email, token, disabled, quota } = account;

  // 检查账号是否被禁用
  if (disabled === true) {
    return { valid: false, reason: '账号已禁用' };
  }

  // 检查是否缺少 token 信息
  if (!token) {
    return { valid: false, reason: '缺少 token 数据' };
  }

  if (!token.access_token) {
    return { valid: false, reason: '缺少 access_token' };
  }

  if (!token.refresh_token) {
    return { valid: false, reason: '缺少 refresh_token' };
  }

  // 检查 token 是否过期（预留 5 分钟缓冲）
  const now = Math.floor(Date.now() / 1000);
  if (token.expiry_timestamp && token.expiry_timestamp < now - 300) {
    return { valid: false, reason: 'Token 已过期' };
  }

  // 检查是否被 403 禁止
  if (quota && quota.is_forbidden === true) {
    return { valid: false, reason: '账号已被禁止访问 (403)' };
  }

  return { valid: true, reason: '' };
}

/**
 * 将 Unix 时间戳（秒）转换为 ISO 8601 格式字符串
 * 格式示例: 2026-01-06T11:35:04+08:00
 */
function timestampToISO(timestamp) {
  const date = new Date(timestamp * 1000);

  // 获取本地时区偏移（分钟）
  const tzOffset = -date.getTimezoneOffset();
  const tzHours = Math.floor(Math.abs(tzOffset) / 60).toString().padStart(2, '0');
  const tzMinutes = (Math.abs(tzOffset) % 60).toString().padStart(2, '0');
  const tzSign = tzOffset >= 0 ? '+' : '-';

  // 构建 ISO 格式字符串（带时区）
  const year = date.getFullYear();
  const month = (date.getMonth() + 1).toString().padStart(2, '0');
  const day = date.getDate().toString().padStart(2, '0');
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  const seconds = date.getSeconds().toString().padStart(2, '0');

  return `${year}-${month}-${day}T${hours}:${minutes}:${seconds}${tzSign}${tzHours}:${tzMinutes}`;
}

/**
 * 将邮箱转换为文件名格式
 * 例如: w154594742@gmail.com -> w154594742_gmail_com
 */
function emailToFileName(email) {
  return email.replace(/@/g, '_').replace(/\./g, '_');
}

/**
 * 转换账号数据为 Antigravity 格式
 */
function convertToAntigravityFormat(account) {
  const { email, token } = account;

  // 验证必要字段
  if (!token || !token.access_token || !token.refresh_token) {
    throw new Error(`账号 ${email} 缺少必要的 token 信息`);
  }

  return {
    access_token: token.access_token,
    email: email,
    expired: timestampToISO(token.expiry_timestamp),
    expires_in: token.expires_in,
    project_id: token.project_id || null,
    refresh_token: token.refresh_token,
    timestamp: Date.now(),
    type: 'antigravity'
  };
}

/**
 * 读取源目录下的所有账号文件
 */
function readSourceAccounts(filterEmail = null) {
  if (!fs.existsSync(SOURCE_DIR)) {
    throw new Error(`源目录不存在: ${SOURCE_DIR}`);
  }

  const files = fs.readdirSync(SOURCE_DIR).filter(f => f.endsWith('.json'));
  const accounts = [];

  for (const file of files) {
    const filePath = path.join(SOURCE_DIR, file);
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      const account = JSON.parse(content);

      // 如果指定了邮箱过滤，只处理匹配的账号
      if (filterEmail && account.email !== filterEmail) {
        continue;
      }

      accounts.push(account);
    } catch (err) {
      console.warn(`⚠️  跳过无效文件: ${file} (${err.message})`);
    }
  }

  return accounts;
}

/**
 * 导出账号到目标目录
 * @param {Array} accounts - 账号列表
 * @param {string} outputDir - 输出目录
 * @param {boolean} includeInvalid - 是否包含无效账号
 */
function exportAccounts(accounts, outputDir, includeInvalid = false) {
  // 确保输出目录存在
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
    console.log(`📁 创建输出目录: ${outputDir}`);
  }

  const results = {
    success: 0,
    failed: 0,
    skipped: 0,
    files: [],
    skippedAccounts: []  // 记录跳过的账号详情
  };

  for (const account of accounts) {
    // 验证账号有效性
    const validation = validateAccount(account);

    if (!validation.valid && !includeInvalid) {
      // 跳过无效账号，记录详情
      results.skipped++;
      results.skippedAccounts.push({
        email: account.email,
        name: account.name || '未知',
        reason: validation.reason
      });
      continue;
    }

    try {
      // 转换格式
      const exported = convertToAntigravityFormat(account);

      // 生成文件名
      const fileName = `antigravity-${emailToFileName(account.email)}.json`;
      const outputPath = path.join(outputDir, fileName);

      // 写入文件
      fs.writeFileSync(outputPath, JSON.stringify(exported, null, 2), 'utf-8');

      results.success++;
      results.files.push(fileName);
      console.log(`✅ ${account.email} -> ${fileName}`);
    } catch (err) {
      results.failed++;
      results.skippedAccounts.push({
        email: account.email,
        name: account.name || '未知',
        reason: `导出错误: ${err.message}`
      });
      console.error(`❌ ${account.email}: ${err.message}`);
    }
  }

  return results;
}

/**
 * 输出跳过账号的详细报告
 */
function printSkippedReport(skippedAccounts) {
  if (skippedAccounts.length === 0) return;

  console.log('\n' + '='.repeat(60));
  console.log('⚠️  跳过的账号详情:');
  console.log('-'.repeat(60));

  // 按原因分组统计
  const reasonGroups = {};
  for (const acc of skippedAccounts) {
    if (!reasonGroups[acc.reason]) {
      reasonGroups[acc.reason] = [];
    }
    reasonGroups[acc.reason].push(acc);
  }

  // 输出每个分组
  for (const [reason, accounts] of Object.entries(reasonGroups)) {
    console.log(`\n【${reason}】(${accounts.length} 个)`);
    for (const acc of accounts) {
      console.log(`   - ${acc.email} (${acc.name})`);
    }
  }
}

/**
 * 主函数
 */
function main() {
  console.log('='.repeat(60));
  console.log('📤 Antigravity 账号导出工具');
  console.log('='.repeat(60));

  const options = parseArgs();
  console.log(`\n📂 源目录: ${SOURCE_DIR}`);
  console.log(`📂 输出目录: ${options.output}`);
  if (options.email) {
    console.log(`📧 过滤邮箱: ${options.email}`);
  }
  if (options.includeInvalid) {
    console.log(`⚙️  模式: 包含无效账号`);
  } else {
    console.log(`⚙️  模式: 仅导出有效账号`);
  }
  console.log('');

  // 读取账号
  const accounts = readSourceAccounts(options.email);
  console.log(`📊 找到 ${accounts.length} 个账号\n`);

  if (accounts.length === 0) {
    console.log('⚠️  没有找到需要导出的账号');
    return;
  }

  // 导出
  const results = exportAccounts(accounts, options.output, options.includeInvalid);

  // 输出跳过账号的详细报告
  printSkippedReport(results.skippedAccounts);

  // 输出统计
  console.log('\n' + '='.repeat(60));
  console.log('📊 导出统计:');
  console.log(`   ✅ 成功: ${results.success}`);
  console.log(`   ⏭️  跳过: ${results.skipped}`);
  console.log(`   ❌ 失败: ${results.failed}`);
  console.log(`📁 输出目录: ${options.output}`);
  console.log('='.repeat(60));
}

// 执行
main();
