#!/usr/bin/env python3
"""
账号数据导出脚本 (Python 版本)
将项目内账号格式转换为 Antigravity 标准格式

使用方法:
  python3 scripts/export-accounts.py [--output <目录>] [--email <邮箱>] [--include-invalid]

参数说明:
  --output <目录>    指定输出目录,默认为 ~/Desktop/antigravity-exports
  --email <邮箱>     仅导出指定邮箱的账号
  --include-invalid  包含无效账号(默认跳过禁用/过期/403账号)

@author wangqiupei
"""

import json
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Tuple, Optional
from collections import defaultdict


# 源数据目录
SOURCE_DIR = Path.home() / '.antigravity_tools' / 'accounts'
# 默认输出目录
DEFAULT_OUTPUT_DIR = Path.home() / 'Desktop' / 'antigravity-exports'


def validate_account(account: dict) -> Tuple[bool, str]:
    """
    验证账号有效性

    Args:
        account: 账号数据字典

    Returns:
        (是否有效, 失败原因)
    """
    email = account.get('email', '未知')
    disabled = account.get('disabled', False)
    token = account.get('token', {})
    quota = account.get('quota', {})

    # 检查账号是否被禁用
    if disabled is True:
        return False, '账号已禁用'

    # 检查是否缺少 token 信息
    if not token:
        return False, '缺少 token 数据'

    access_token = token.get('access_token')
    if not access_token:
        return False, '缺少 access_token'

    refresh_token = token.get('refresh_token')
    if not refresh_token:
        return False, '缺少 refresh_token'

    # 检查 token 是否过期(预留 5 分钟缓冲)
    expiry_timestamp = token.get('expiry_timestamp')
    if expiry_timestamp:
        now = int(datetime.now().timestamp())
        if expiry_timestamp < now - 300:
            return False, 'Token 已过期'

    # 检查是否被 403 禁止
    is_forbidden = quota.get('is_forbidden', False)
    if is_forbidden is True:
        return False, '账号已被禁止访问 (403)'

    return True, ''


def timestamp_to_iso8601(timestamp: int) -> str:
    """
    将 Unix 时间戳(秒)转换为 ISO 8601 格式字符串
    格式示例: 2026-01-06T11:35:04+08:00

    Args:
        timestamp: Unix 时间戳(秒)

    Returns:
        ISO 8601 格式时间字符串
    """
    # 使用本地时区
    dt = datetime.fromtimestamp(timestamp)
    # 格式化为 ISO 8601 (带时区偏移)
    return dt.astimezone().isoformat()


def email_to_filename(email: str) -> str:
    """
    将邮箱转换为文件名格式
    例如: w154594742@gmail.com -> w154594742_gmail_com

    Args:
        email: 邮箱地址

    Returns:
        文件名格式字符串
    """
    return email.replace('@', '_').replace('.', '_')


def convert_to_antigravity_format(account: dict) -> dict:
    """
    转换账号数据为 Antigravity 格式

    Args:
        account: 原始账号数据

    Returns:
        Antigravity 标准格式数据

    Raises:
        ValueError: 缺少必要字段时抛出
    """
    email = account.get('email', '')
    token = account.get('token', {})

    access_token = token.get('access_token')
    refresh_token = token.get('refresh_token')

    # 验证必要字段
    if not access_token or not refresh_token:
        raise ValueError(f'账号 {email} 缺少必要的 token 信息')

    expiry_timestamp = token.get('expiry_timestamp', 0)

    return {
        'access_token': access_token,
        'email': email,
        'expired': timestamp_to_iso8601(expiry_timestamp),
        'expires_in': token.get('expires_in'),
        'project_id': token.get('project_id'),
        'refresh_token': refresh_token,
        'timestamp': int(datetime.now().timestamp() * 1000),  # 毫秒时间戳
        'type': 'antigravity'
    }


def read_source_accounts(filter_email: Optional[str] = None) -> List[dict]:
    """
    读取源目录下的所有账号文件

    Args:
        filter_email: 可选的邮箱过滤条件

    Returns:
        账号数据列表

    Raises:
        FileNotFoundError: 源目录不存在时抛出
    """
    if not SOURCE_DIR.exists():
        raise FileNotFoundError(f'源目录不存在: {SOURCE_DIR}')

    accounts = []
    json_files = SOURCE_DIR.glob('*.json')

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                account = json.load(f)

            # 如果指定了邮箱过滤,只处理匹配的账号
            if filter_email and account.get('email') != filter_email:
                continue

            accounts.append(account)
        except (json.JSONDecodeError, IOError) as e:
            print(f'⚠️  跳过无效文件: {file_path.name} ({e})')

    return accounts


def export_accounts(accounts: List[dict], output_dir: Path, include_invalid: bool = False) -> dict:
    """
    导出账号到目标目录

    Args:
        accounts: 账号列表
        output_dir: 输出目录
        include_invalid: 是否包含无效账号

    Returns:
        导出结果统计字典
    """
    # 确保输出目录存在
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f'📁 创建输出目录: {output_dir}')

    results = {
        'success': 0,
        'failed': 0,
        'skipped': 0,
        'files': [],
        'skipped_accounts': []  # 记录跳过的账号详情
    }

    for account in accounts:
        email = account.get('email', '未知')
        name = account.get('name', '未知')

        # 验证账号有效性
        is_valid, reason = validate_account(account)

        if not is_valid and not include_invalid:
            # 跳过无效账号,记录详情
            results['skipped'] += 1
            results['skipped_accounts'].append({
                'email': email,
                'name': name,
                'reason': reason
            })
            continue

        try:
            # 转换格式
            exported = convert_to_antigravity_format(account)

            # 生成文件名
            filename = f'antigravity-{email_to_filename(email)}.json'
            output_path = output_dir / filename

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(exported, f, ensure_ascii=False, indent=2)

            results['success'] += 1
            results['files'].append(filename)
            print(f'✅ {email} -> {filename}')
        except (ValueError, IOError) as e:
            results['failed'] += 1
            results['skipped_accounts'].append({
                'email': email,
                'name': name,
                'reason': f'导出错误: {e}'
            })
            print(f'❌ {email}: {e}')

    return results


def print_skipped_report(skipped_accounts: List[dict]) -> None:
    """
    输出跳过账号的详细报告

    Args:
        skipped_accounts: 跳过的账号列表
    """
    if not skipped_accounts:
        return

    print('\n' + '=' * 60)
    print('⚠️  跳过的账号详情:')
    print('-' * 60)

    # 按原因分组统计
    reason_groups = defaultdict(list)
    for acc in skipped_accounts:
        reason = acc['reason']
        reason_groups[reason].append(acc)

    # 输出每个分组
    for reason, accounts in reason_groups.items():
        print(f'\n【{reason}】({len(accounts)} 个)')
        for acc in accounts:
            print(f'   - {acc["email"]} ({acc["name"]})')


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数

    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description='Antigravity 账号导出工具 (Python 版本)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f'指定输出目录,默认为 {DEFAULT_OUTPUT_DIR}'
    )

    parser.add_argument(
        '--email',
        type=str,
        default=None,
        help='仅导出指定邮箱的账号'
    )

    parser.add_argument(
        '--include-invalid',
        action='store_true',
        help='包含无效账号(默认跳过禁用/过期/403账号)'
    )

    return parser.parse_args()


def main() -> None:
    """主函数"""
    print('=' * 60)
    print('📤 Antigravity 账号导出工具 (Python 版本)')
    print('=' * 60)

    args = parse_args()

    print(f'\n📂 源目录: {SOURCE_DIR}')
    print(f'📂 输出目录: {args.output}')
    if args.email:
        print(f'📧 过滤邮箱: {args.email}')
    if args.include_invalid:
        print('⚙️  模式: 包含无效账号')
    else:
        print('⚙️  模式: 仅导出有效账号')
    print()

    try:
        # 读取账号
        accounts = read_source_accounts(args.email)
        print(f'📊 找到 {len(accounts)} 个账号\n')

        if not accounts:
            print('⚠️  没有找到需要导出的账号')
            return

        # 导出
        results = export_accounts(accounts, args.output, args.include_invalid)

        # 输出跳过账号的详细报告
        print_skipped_report(results['skipped_accounts'])

        # 输出统计
        print('\n' + '=' * 60)
        print('📊 导出统计:')
        print(f'   ✅ 成功: {results["success"]}')
        print(f'   ⏭️  跳过: {results["skipped"]}')
        print(f'   ❌ 失败: {results["failed"]}')
        print(f'📁 输出目录: {args.output}')
        print('=' * 60)

    except FileNotFoundError as e:
        print(f'❌ 错误: {e}', file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print('\n\n⚠️  用户中断操作')
        sys.exit(130)
    except Exception as e:
        print(f'❌ 未预期的错误: {e}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
