#!/usr/bin/env python3
"""
Antigravity Manager → AIClient-2-API 格式导出脚本

功能：将 Antigravity Manager 账号凭证转换为 AIClient-2-API 格式的 JSON 文件
目标格式特征：文件名包含毫秒时间戳，邮箱中的特殊字符替换为下划线

使用方法:
  python3 scripts/export-to-aiclient2api.py [--output-dir <目录>] [--include-invalid] [--dry-run] [--verbose]

@author wangqiupei
"""

import os
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import argparse
from collections import defaultdict


# ==================== 配置常量 ====================

# Antigravity OAuth 配置
ANTIGRAVITY_CLIENT_ID = "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com"
ANTIGRAVITY_CLIENT_SECRET = "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"
ANTIGRAVITY_SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/cclog',
    'https://www.googleapis.com/auth/experimentsandconfigs'
]
TOKEN_URI = "https://oauth2.googleapis.com/token"

# 默认导出目录
DEFAULT_EXPORT_DIR = Path.home() / "Downloads" / "aiclient2api"

# Antigravity Manager 数据目录名称
DATA_DIR_NAME = ".antigravity_tools"
ACCOUNTS_INDEX_FILE = "accounts.json"
ACCOUNTS_DIR_NAME = "accounts"

# Token 过期缓冲时间（秒）- 预留 5 分钟
TOKEN_EXPIRY_BUFFER = 300


# ==================== 数据读取模块 ====================

def get_data_dir() -> Path:
    """
    获取 Antigravity Manager 数据目录

    Returns:
        数据目录路径

    Raises:
        FileNotFoundError: 数据目录不存在
    """
    data_dir = Path.home() / DATA_DIR_NAME
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Antigravity Manager 数据目录不存在: {data_dir}\n"
            f"请确保已经使用过 Antigravity Manager 并添加了账号。"
        )
    return data_dir


def load_account_index() -> dict:
    """
    加载账号索引文件

    Returns:
        账号索引数据（包含 accounts 列表）

    Raises:
        FileNotFoundError: 索引文件不存在
        json.JSONDecodeError: 索引文件格式错误
    """
    data_dir = get_data_dir()
    index_path = data_dir / ACCOUNTS_INDEX_FILE

    if not index_path.exists():
        raise FileNotFoundError(
            f"账号索引文件不存在: {index_path}\n"
            f"请确保已经通过 Antigravity Manager 添加了账号。"
        )

    with open(index_path, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    return index_data


def load_account(account_id: str) -> dict:
    """
    加载单个账号的详细数据

    Args:
        account_id: 账号 ID

    Returns:
        账号详细数据

    Raises:
        FileNotFoundError: 账号文件不存在
        json.JSONDecodeError: 账号文件格式错误
    """
    data_dir = get_data_dir()
    accounts_dir = data_dir / ACCOUNTS_DIR_NAME
    account_path = accounts_dir / f"{account_id}.json"

    if not account_path.exists():
        raise FileNotFoundError(f"账号文件不存在: {account_path}")

    with open(account_path, 'r', encoding='utf-8') as f:
        account_data = json.load(f)

    return account_data


# ==================== 账号验证模块 ====================

def validate_account(account: dict) -> tuple:
    """
    验证账号有效性

    Args:
        account: 账号数据

    Returns:
        (是否有效, 失败原因) 元组
    """
    # 检查账号是否被禁用
    if account.get('disabled') is True:
        return False, '账号已禁用'

    # 检查 token 数据
    token = account.get('token')
    if not token:
        return False, '缺少 token 数据'

    # 检查必需的 token 字段
    if not token.get('access_token'):
        return False, '缺少 access_token'

    if not token.get('refresh_token'):
        return False, '缺少 refresh_token'

    # 检查 Token 是否过期（预留 5 分钟缓冲）
    expiry_timestamp = token.get('expiry_timestamp', 0)
    current_timestamp = datetime.now(timezone.utc).timestamp()

    if expiry_timestamp < (current_timestamp - TOKEN_EXPIRY_BUFFER):
        return False, 'Token 已过期'

    # 检查是否被 403 禁止访问
    quota = account.get('quota')
    if quota and quota.get('is_forbidden') is True:
        return False, '账号已被禁止访问 (403)'

    return True, ''


# ==================== 数据转换模块 ====================

def convert_timestamp_to_iso(timestamp: int) -> str:
    """
    将 Unix 时间戳转换为 ISO 8601 格式（带时区）

    Args:
        timestamp: Unix 时间戳（秒）

    Returns:
        ISO 8601 格式的时间字符串，例如 "2026-01-17T02:30:45+00:00"
    """
    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
    return dt.isoformat()


def convert_to_credential_format(account: dict) -> dict:
    """
    将 Antigravity Manager 账号数据转换为 AIClient-2-API 凭证格式

    Args:
        account: Antigravity Manager 账号数据

    Returns:
        AIClient-2-API 格式的凭证数据
    """
    token = account['token']

    # 构建凭证数据（与 gcli2api 格式相同）
    credential = {
        "client_id": ANTIGRAVITY_CLIENT_ID,
        "client_secret": ANTIGRAVITY_CLIENT_SECRET,
        "token": token['access_token'],
        "refresh_token": token['refresh_token'],
        "scopes": ANTIGRAVITY_SCOPES,
        "token_uri": TOKEN_URI,
        "project_id": token.get('project_id', ''),
        "expiry": convert_timestamp_to_iso(token['expiry_timestamp'])
    }

    return credential


# ==================== 文件命名模块 ====================

def convert_email_to_filename_part(email: str) -> str:
    """
    将邮箱地址转换为文件名组成部分
    规则：@ 和 . 替换为下划线

    Args:
        email: 邮箱地址，例如 "haris.huang.1987@gmail.com"

    Returns:
        转换后的字符串，例如 "haris_huang_1987_gmail_com"
    """
    # 将 @ 和 . 替换为下划线
    result = email.replace('@', '_').replace('.', '_')
    return result


def generate_filename(email: str) -> str:
    """
    生成 AIClient-2-API 格式的文件名
    格式：{毫秒时间戳}_antigravity_{邮箱转换}.json

    Args:
        email: 账号邮箱

    Returns:
        完整的文件名，例如 "1770174644982_antigravity_haris_huang_1987_gmail_com.json"
    """
    # 获取当前毫秒时间戳
    timestamp_ms = int(time.time() * 1000)

    # 转换邮箱为文件名部分
    email_part = convert_email_to_filename_part(email)

    # 组合文件名
    filename = f"{timestamp_ms}_antigravity_{email_part}.json"

    return filename


# ==================== 文件导出模块 ====================

def ensure_export_dir(output_dir: Path) -> None:
    """
    确保导出目录存在，如果不存在则创建

    Args:
        output_dir: 导出目录路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)


def export_credential(cred_data: dict, output_dir: Path, email: str) -> tuple:
    """
    导出单个凭证文件

    Args:
        cred_data: 凭证数据
        output_dir: 导出目录
        email: 账号邮箱（用于生成文件名）

    Returns:
        (是否成功, 文件路径或错误信息) 元组
    """
    try:
        # 生成文件名
        filename = generate_filename(email)
        file_path = output_dir / filename

        # 写入 JSON 文件（格式化输出）
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(cred_data, f, ensure_ascii=False, indent=2)

        return True, str(file_path)

    except Exception as e:
        return False, f"写入文件失败: {e}"


# ==================== 报告输出模块 ====================

def print_banner():
    """打印欢迎横幅"""
    print("\n" + "=" * 70)
    print("  Antigravity Manager → AIClient-2-API 凭证导出工具")
    print("=" * 70 + "\n")


def print_skipped_report(skipped_accounts: list):
    """
    输出跳过账号的详细报告

    Args:
        skipped_accounts: 跳过的账号列表，每项包含 (email, name, reason)
    """
    if not skipped_accounts:
        return

    print("\n" + "=" * 70)
    print("⚠️  跳过的账号详情:")
    print("-" * 70)

    # 按原因分组统计
    reason_groups = defaultdict(list)
    for email, name, reason in skipped_accounts:
        reason_groups[reason].append((email, name))

    # 输出每个分组
    for reason, accounts in reason_groups.items():
        print(f"\n【{reason}】({len(accounts)} 个)")
        for email, name in accounts:
            display_name = name if name else '未知'
            print(f"   - {email} ({display_name})")


def print_summary(success_count: int, failed_count: int, skipped_count: int, output_dir: Path):
    """
    打印导出摘要

    Args:
        success_count: 成功导出的凭证数量
        failed_count: 失败的凭证数量
        skipped_count: 跳过的凭证数量
        output_dir: 导出目录
    """
    print("\n" + "=" * 70)
    print("  导出完成")
    print("=" * 70)
    print(f"  ✅ 成功: {success_count} 个")
    print(f"  ⏭️  跳过: {skipped_count} 个")
    print(f"  ❌ 失败: {failed_count} 个")
    print(f"  📁 导出位置: {output_dir}")
    print("=" * 70 + "\n")

    if success_count > 0:
        print("💡 下一步：")
        print("   1. 将导出的 JSON 文件复制到 AIClient-2-API 项目的凭证目录")
        print("   2. 目标路径示例: docker/configs/antigravity/")
        print("   3. 重启 AIClient-2-API 服务以加载新凭证\n")


# ==================== 主流程控制 ====================

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="将 Antigravity Manager 凭证导出为 AIClient-2-API 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 基本使用（导出有效账号到默认目录）
  python3 scripts/export-to-aiclient2api.py

  # 包含所有账号（包括无效账号）
  python3 scripts/export-to-aiclient2api.py --include-invalid

  # 自定义输出目录
  python3 scripts/export-to-aiclient2api.py --output-dir /path/to/output

  # 试运行（不写入文件，仅显示将要执行的操作）
  python3 scripts/export-to-aiclient2api.py --dry-run

  # 详细输出
  python3 scripts/export-to-aiclient2api.py --verbose
        """
    )

    parser.add_argument(
        '--output-dir',
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help=f'导出目录（默认: {DEFAULT_EXPORT_DIR}）'
    )

    parser.add_argument(
        '--include-invalid',
        action='store_true',
        help='包含无效账号（默认跳过禁用/过期/403账号）'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='试运行模式（不写入文件）'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细输出'
    )

    args = parser.parse_args()

    # 打印欢迎信息
    print_banner()

    try:
        # 1. 显示配置信息
        data_dir = get_data_dir()
        print(f"📂 数据目录: {data_dir}")
        print(f"📤 导出目录: {args.output_dir}")
        if args.dry_run:
            print("🔍 模式: 试运行（不会写入文件）")
        if args.include_invalid:
            print("⚙️  模式: 包含无效账号")
        else:
            print("⚙️  模式: 仅导出有效账号")
        print()

        # 2. 加载账号索引
        print("正在加载账号索引...")
        index_data = load_account_index()
        accounts_list = index_data.get('accounts', [])

        if not accounts_list:
            print("❌ 未找到任何账号。请先在 Antigravity Manager 中添加账号。")
            return 1

        print(f"✓ 找到 {len(accounts_list)} 个账号\n")

        # 3. 创建导出目录（非试运行模式）
        if not args.dry_run:
            ensure_export_dir(args.output_dir)

        # 4. 遍历所有账号进行转换
        print("正在转换凭证...")
        success_count = 0
        failed_count = 0
        skipped_count = 0
        skipped_accounts = []  # 记录跳过的账号：(email, name, reason)
        results = []

        for account_summary in accounts_list:
            account_id = account_summary['id']
            email = account_summary['email']
            name = account_summary.get('name', '')

            try:
                # 加载账号详细数据
                if args.verbose:
                    print(f"\n处理账号: {email}")

                account = load_account(account_id)

                # 验证账号有效性
                is_valid, reason = validate_account(account)

                if not is_valid and not args.include_invalid:
                    # 跳过无效账号
                    skipped_count += 1
                    skipped_accounts.append((email, name, reason))
                    if args.verbose:
                        print(f"  ⏭️  跳过: {reason}")
                    continue

                # 转换为凭证格式
                credential = convert_to_credential_format(account)

                # 导出凭证文件
                if args.dry_run:
                    filename = generate_filename(email)
                    print(f"  [试运行] 将导出: {filename}")
                    success_count += 1
                    results.append((email, True, filename))
                else:
                    success, result = export_credential(credential, args.output_dir, email)

                    if success:
                        filename = Path(result).name
                        print(f"  ✓ {email} → {filename}")
                        success_count += 1
                        results.append((email, True, filename))
                    else:
                        print(f"  ✗ {email} - {result}")
                        failed_count += 1
                        results.append((email, False, result))

            except Exception as e:
                error_msg = f"处理失败: {e}"
                print(f"  ✗ {email} - {error_msg}")
                failed_count += 1
                results.append((email, False, error_msg))

        # 5. 输出跳过账号的详细报告
        print_skipped_report(skipped_accounts)

        # 6. 打印摘要
        print_summary(success_count, failed_count, skipped_count, args.output_dir)

        # 7. 详细结果（仅在详细模式下）
        if args.verbose and results:
            print("\n详细结果:")
            for email, success, detail in results:
                status = "✓" if success else "✗"
                print(f"  {status} {email}: {detail}")
            print()

        return 0 if failed_count == 0 else 1

    except FileNotFoundError as e:
        print(f"\n❌ 错误: {e}\n")
        return 1

    except json.JSONDecodeError as e:
        print(f"\n❌ JSON 解析错误: {e}")
        print("请检查数据文件是否损坏。\n")
        return 1

    except Exception as e:
        print(f"\n❌ 未预期的错误: {e}\n")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
