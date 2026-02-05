#!/usr/bin/env python3
"""
Antigravity Manager → Antigravity2api-nodejs 格式导出脚本

功能：将 Antigravity Manager 账号凭证转换为 Antigravity2api-nodejs 格式的 JSON 文件
目标格式特征：
  - 每个账号导出为单独的 JSON 文件
  - timestamp + expires_in 分开存储，projectId 驼峰命名
  - 包含 hasQuota 字段用于配额管理
  - 文件可直接拖入 antigravity2api-nodejs 的"添加/导入 Token"弹窗使用

使用方法:
  python3 scripts/export-to-Antigravity2api-nodejs.py [选项]

参数说明:
  --output <目录>       指定输出目录，默认为 ~/Downloads/Antigravity2api-nodejs
  --start <索引>        起始账号索引（包含），用于非交互模式
  --end <索引>          结束账号索引（包含），用于非交互模式
  -n, --no-interactive  禁用交互模式（用于脚本自动化）
  --include-invalid     包含无效账号（默认跳过禁用/过期/403账号）
  --dry-run             试运行模式（不写入文件）
  --verbose             显示详细输出
  --list                仅列出账号索引（不导出）

交互模式（默认）:
  直接运行脚本会进入交互模式，显示账号列表后让你选择导出范围

非交互模式:
  使用 --start/--end 或 -n 参数时自动切换为非交互模式

示例:
  # 交互式选择账号（默认）
  python3 scripts/export-to-Antigravity2api-nodejs.py

  # 非交互模式：导出索引 0-9 的账号
  python3 scripts/export-to-Antigravity2api-nodejs.py --start 0 --end 9

  # 非交互模式：导出全部账号
  python3 scripts/export-to-Antigravity2api-nodejs.py -n

  # 列出所有账号及其索引
  python3 scripts/export-to-Antigravity2api-nodejs.py --list

@author wangqiupei
"""

import json
import sys
import secrets
from datetime import datetime, timezone
from pathlib import Path
import argparse
from collections import defaultdict
from typing import Tuple, List, Optional, Set


# ==================== 配置常量 ====================

# 默认导出目录
DEFAULT_EXPORT_DIR = Path.home() / "Downloads" / "Antigravity2api-nodejs"

# Antigravity Manager 数据目录配置
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

def validate_account(account: dict) -> Tuple[bool, str]:
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

def convert_to_nodejs_format(account: dict) -> dict:
    """
    将 Antigravity Manager 账号数据转换为 Antigravity2api-nodejs 凭证格式

    关键字段映射：
    - expiry_timestamp (秒) → timestamp (毫秒，令牌获取时间)
    - project_id → projectId (驼峰命名)
    - 新增 enable: true

    Args:
        account: Antigravity Manager 账号数据

    Returns:
        Antigravity2api-nodejs 格式的凭证数据
    """
    token = account['token']

    # 计算 timestamp（令牌获取时间 = 过期时间 - 有效期）
    expiry_timestamp = token.get('expiry_timestamp', 0)
    expires_in = token.get('expires_in', 3599)
    # 转换为毫秒时间戳
    token_timestamp = (expiry_timestamp - expires_in) * 1000

    # 构建 Antigravity2api-nodejs 格式的凭证数据
    nodejs_cred = {
        "access_token": token['access_token'],
        "refresh_token": token['refresh_token'],
        "expires_in": expires_in,
        "timestamp": int(token_timestamp),
        "email": account.get('email', ''),
        "projectId": token.get('project_id', ''),  # 驼峰命名
        "enable": True,
        "hasQuota": True  # 有效账号默认有配额，避免首次请求时的配额检查
    }

    return nodejs_cred


# ==================== 文件导出模块 ====================

def generate_salt() -> str:
    """
    生成随机盐值，与 antigravity2api-nodejs 的实现保持一致

    Returns:
        32字节的十六进制盐值（64个字符）
    """
    return secrets.token_hex(32)


def ensure_export_dir(output_dir: Path) -> None:
    """
    确保导出目录存在，如果不存在则创建

    Args:
        output_dir: 导出目录路径
    """
    output_dir.mkdir(parents=True, exist_ok=True)


def sanitize_filename(email: str) -> str:
    """
    清理邮箱地址以生成安全的文件名
    例如: w154594742@gmail.com -> w154594742_gmail_com

    Args:
        email: 邮箱地址

    Returns:
        安全的文件名（@ 替换为 _，. 替换为 _）
    """
    return email.replace('@', '_').replace('.', '_')


def export_single_credential(
    cred_data: dict,
    output_dir: Path,
    email: str
) -> Tuple[bool, str]:
    """
    导出单个凭证文件

    Args:
        cred_data: 凭证数据（Antigravity2api-nodejs 格式）
        output_dir: 导出目录
        email: 账号邮箱（用于生成文件名）

    Returns:
        (是否成功, 文件路径或错误信息) 元组
    """
    try:
        # 生成安全的文件名
        safe_email = sanitize_filename(email)
        filename = f"antigravity-{safe_email}.json"
        file_path = output_dir / filename

        # 写入 JSON 文件（格式化输出）
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(cred_data, f, ensure_ascii=False, indent=2)

        # 设置文件权限为仅所有者读写
        file_path.chmod(0o600)

        return True, str(file_path)

    except Exception as e:
        return False, f"写入文件失败: {e}"


def export_accounts_array(
    accounts_data: List[dict],
    output_file: Path
) -> Tuple[bool, str]:
    """
    导出账号数组到单个 JSON 文件（带 salt 的新格式）

    Args:
        accounts_data: 账号数据列表（Antigravity2api-nodejs 格式）
        output_file: 导出文件路径

    Returns:
        (是否成功, 文件路径或错误信息) 元组
    """
    try:
        # 确保目录存在
        output_dir = output_file.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        # 构建带 salt 的输出数据
        output_data = {
            "salt": generate_salt(),
            "tokens": accounts_data
        }

        # 写入 JSON 文件（格式化输出）
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        # 设置文件权限为仅所有者读写
        output_file.chmod(0o600)

        return True, str(output_file)

    except Exception as e:
        return False, f"写入文件失败: {e}"


# ==================== 报告输出模块 ====================

def print_banner():
    """打印欢迎横幅"""
    print("\n" + "=" * 70)
    print("  Antigravity Manager → Antigravity2api-nodejs 凭证导出工具")
    print("=" * 70 + "\n")


def print_accounts_preview(accounts_list: List[dict], include_invalid: bool = False) -> None:
    """
    打印账号预览表（带索引）

    Args:
        accounts_list: 账号索引列表
        include_invalid: 是否包含无效账号
    """
    print("\n" + "-" * 70)
    print(f"{'索引':<6} {'邮箱':<35} {'状态':<15}")
    print("-" * 70)

    for idx, account_summary in enumerate(accounts_list):
        email = account_summary.get('email', '未知')
        account_id = account_summary.get('id', '')

        # 尝试加载账号详情以验证状态
        try:
            account = load_account(account_id)
            is_valid, reason = validate_account(account)
            status = "✓ 有效" if is_valid else f"✗ {reason}"
        except Exception as e:
            status = f"✗ 加载失败"

        print(f"{idx:<6} {email:<35} {status:<15}")

    print("-" * 70 + "\n")


# ==================== 交互式选择模块 ====================

def parse_range_input(input_str: str, max_index: int) -> Optional[Set[int]]:
    """
    解析用户输入的范围字符串

    支持格式:
    - 连续范围: "0-9"
    - 单个索引: "0,3,5,8"
    - 混合模式: "0-5,8,10-12"
    - 全部: "all" 或空字符串

    Args:
        input_str: 用户输入的范围字符串
        max_index: 最大有效索引

    Returns:
        选中的索引集合，None 表示取消
    """
    input_str = input_str.strip().lower()

    # 取消操作
    if input_str in ('q', 'quit', 'exit'):
        return None

    # 全部导出
    if input_str in ('all', ''):
        return set(range(max_index + 1))

    selected = set()
    parts = input_str.split(',')

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 检查是否是范围格式 (如 "0-9")
        if '-' in part:
            try:
                range_parts = part.split('-')
                if len(range_parts) != 2:
                    print(f"  ⚠️  无效的范围格式: {part}")
                    continue
                start = int(range_parts[0].strip())
                end = int(range_parts[1].strip())

                # 验证范围有效性
                if start < 0 or end > max_index or start > end:
                    print(f"  ⚠️  范围超出有效索引 (0-{max_index}): {part}")
                    continue

                selected.update(range(start, end + 1))
            except ValueError:
                print(f"  ⚠️  无效的数字: {part}")
                continue
        else:
            # 单个索引
            try:
                idx = int(part)
                if idx < 0 or idx > max_index:
                    print(f"  ⚠️  索引超出范围 (0-{max_index}): {idx}")
                    continue
                selected.add(idx)
            except ValueError:
                print(f"  ⚠️  无效的数字: {part}")
                continue

    return selected if selected else None


def interactive_select(accounts_list: List[dict], include_invalid: bool = False) -> Optional[List[int]]:
    """
    交互式选择要导出的账号

    Args:
        accounts_list: 账号索引列表
        include_invalid: 是否包含无效账号

    Returns:
        选中的账号索引列表（已排序），None 表示取消
    """
    total = len(accounts_list)
    max_index = total - 1

    # 显示账号列表
    print_accounts_preview(accounts_list, include_invalid)

    # 显示输入提示
    print("请输入要导出的账号范围:")
    print("  - 连续范围: 0-9")
    print("  - 单个索引: 0,3,5,8")
    print("  - 混合模式: 0-5,8,10-12")
    print("  - 全部导出: all 或直接回车")
    print("  - 取消: q")
    print()

    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n⚠️  操作已取消")
            return None

        selected = parse_range_input(user_input, max_index)

        if selected is None:
            print("\n⚠️  操作已取消")
            return None

        if not selected:
            print("  ⚠️  未选择任何账号，请重新输入")
            continue

        # 排序并转换为列表
        selected_list = sorted(selected)

        # 显示选中的账号预览
        print(f"\n已选择 {len(selected_list)} 个账号:")
        preview_count = min(5, len(selected_list))
        for i in range(preview_count):
            idx = selected_list[i]
            email = accounts_list[idx].get('email', '未知')
            print(f"  [{idx}] {email}")
        if len(selected_list) > 5:
            print(f"  ... 还有 {len(selected_list) - 5} 个账号")

        # 确认
        print()
        try:
            confirm = input(f"确认导出这 {len(selected_list)} 个账号？[Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n\n⚠️  操作已取消")
            return None

        if confirm in ('', 'y', 'yes'):
            return selected_list
        elif confirm in ('n', 'no'):
            print("\n请重新选择范围:")
            continue
        else:
            # 默认确认
            return selected_list


def interactive_select_export_format() -> Optional[str]:
    """
    交互式选择导出格式

    Returns:
        'single' - 单个 accounts.json 文件
        'multiple' - 每个账号单独文件
        None - 用户取消
    """
    print("\n请选择导出格式:")
    print("  [1] 单个 accounts.json 文件（适合批量导入）")
    print("  [2] 每个账号单独文件（适合拖拽导入）")
    print("  [q] 取消")
    print()

    while True:
        try:
            choice = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n\n⚠️  操作已取消")
            return None

        if choice == 'q':
            print("\n⚠️  操作已取消")
            return None
        elif choice in ('1', 'single', '单个'):
            return 'single'
        elif choice in ('2', 'multiple', '多个', ''):
            return 'multiple'
        else:
            print("  ⚠️  请输入 1 或 2")


def print_skipped_report(skipped_accounts: List[Tuple[str, str, str]]) -> None:
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


def print_summary(success_count: int, failed_count: int, skipped_count: int,
                  output_path: Path, total_in_range: int, export_format: str = 'multiple'):
    """
    打印导出摘要

    Args:
        success_count: 成功导出的凭证数量
        failed_count: 失败的凭证数量
        skipped_count: 跳过的凭证数量
        output_path: 导出路径（目录或文件）
        total_in_range: 范围内的总账号数
        export_format: 导出格式 ('single' 或 'multiple')
    """
    print("\n" + "=" * 70)
    print("  导出完成")
    print("=" * 70)
    print(f"  📊 范围内账号: {total_in_range} 个")
    print(f"  ✅ 成功导出: {success_count} 个")
    print(f"  ⏭️  跳过: {skipped_count} 个")
    print(f"  ❌ 失败: {failed_count} 个")

    if export_format == 'single':
        print(f"  📁 导出文件: {output_path}")
    else:
        print(f"  📁 导出目录: {output_path}")
    print("=" * 70 + "\n")

    if success_count > 0:
        print("💡 下一步：")
        print("   1. 打开 Antigravity2api-nodejs 管理界面")
        print("   2. 点击「添加/导入 Token」按钮")
        print("   3. 将导出的 JSON 文件拖入弹窗中导入\n")


# ==================== 主流程控制 ====================

def parse_args() -> argparse.Namespace:
    """
    解析命令行参数

    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description="将 Antigravity Manager 凭证导出为 Antigravity2api-nodejs 格式（每账户单独文件）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 交互式选择账号（默认）
  python3 scripts/export-to-Antigravity2api-nodejs.py

  # 非交互模式：导出索引 0-9 的账号
  python3 scripts/export-to-Antigravity2api-nodejs.py --start 0 --end 9

  # 非交互模式：导出全部账号
  python3 scripts/export-to-Antigravity2api-nodejs.py -n

  # 列出所有账号及其索引
  python3 scripts/export-to-Antigravity2api-nodejs.py --list

  # 自定义输出目录
  python3 scripts/export-to-Antigravity2api-nodejs.py --output ~/Desktop/tokens
        """
    )

    parser.add_argument(
        '--output',
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help=f'导出目录（默认: {DEFAULT_EXPORT_DIR}）'
    )

    parser.add_argument(
        '--start',
        type=int,
        default=None,
        help='起始账号索引（包含），指定后自动切换为非交互模式'
    )

    parser.add_argument(
        '--end',
        type=int,
        default=None,
        help='结束账号索引（包含），指定后自动切换为非交互模式'
    )

    parser.add_argument(
        '-n', '--no-interactive',
        action='store_true',
        help='禁用交互模式（用于脚本自动化，默认导出全部账号）'
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

    parser.add_argument(
        '--list',
        action='store_true',
        help='仅列出账号索引（不导出）'
    )

    return parser.parse_args()


def main() -> int:
    """
    主函数

    Returns:
        退出码（0 表示成功，非 0 表示失败）
    """
    args = parse_args()

    # 判断是否使用交互模式
    # 指定 --start/--end/--list/-n 时自动切换为非交互模式
    use_interactive = not (
        args.no_interactive or
        args.start is not None or
        args.end is not None or
        args.list
    )

    # 打印欢迎信息
    print_banner()

    try:
        # 1. 显示配置信息
        data_dir = get_data_dir()
        print(f"📂 数据目录: {data_dir}")

        if not args.list:
            print(f"📤 导出目录: {args.output}")
            if args.dry_run:
                print("🔍 模式: 试运行（不会写入文件）")
            if args.include_invalid:
                print("⚙️  模式: 包含无效账号")
            else:
                print("⚙️  模式: 仅导出有效账号")
            if use_interactive:
                print("🖱️  模式: 交互式选择")
            print("📄 格式: 每账户单独文件")
        print()

        # 2. 加载账号索引
        print("正在加载账号索引...")
        index_data = load_account_index()
        accounts_list = index_data.get('accounts', [])

        if not accounts_list:
            print("❌ 未找到任何账号。请先在 Antigravity Manager 中添加账号。")
            return 1

        total_accounts = len(accounts_list)
        print(f"✓ 找到 {total_accounts} 个账号")

        # 3. 如果是列表模式，显示账号列表后退出
        if args.list:
            print_accounts_preview(accounts_list, args.include_invalid)
            print(f"💡 使用 --start 和 --end 参数指定导出范围")
            print(f"   例如: --start 0 --end 9 导出前 10 个账号")
            return 0

        # 4. 确定要导出的账号索引和导出格式
        export_format = 'multiple'  # 默认为多文件模式

        if use_interactive:
            # 交互式选择账号
            selected_indices = interactive_select(accounts_list, args.include_invalid)
            if selected_indices is None:
                return 0  # 用户取消

            # 根据选中的索引获取账号
            range_accounts = [(idx, accounts_list[idx]) for idx in selected_indices]
            total_in_range = len(range_accounts)
            print(f"\n📊 已选择 {total_in_range} 个账号")

            # 交互式选择导出格式
            export_format = interactive_select_export_format()
            if export_format is None:
                return 0  # 用户取消

            if export_format == 'single':
                print("\n📄 导出格式: 单个 accounts.json 文件")
            else:
                print("\n📄 导出格式: 每账户单独文件")
            print()
        else:
            # 非交互模式：使用 --start/--end 参数
            start_idx = args.start if args.start is not None else 0
            start_idx = max(0, start_idx)
            end_idx = args.end if args.end is not None else total_accounts - 1
            end_idx = min(end_idx, total_accounts - 1)

            if start_idx > end_idx:
                print(f"❌ 无效的范围: start={start_idx}, end={end_idx}")
                return 1

            range_accounts = [(i, accounts_list[i]) for i in range(start_idx, end_idx + 1)]
            total_in_range = len(range_accounts)
            print(f"📊 导出范围: 索引 {start_idx} - {end_idx}（共 {total_in_range} 个账号）\n")

        # 5. 详细模式下显示账号预览（非交互模式）
        if args.verbose and not use_interactive:
            print("账号预览:")
            preview_list = [acc for _, acc in range_accounts]
            print_accounts_preview(preview_list, args.include_invalid)

        # 6. 创建导出目录（非试运行模式）
        if not args.dry_run:
            ensure_export_dir(args.output)

        # 7. 遍历选中账号进行转换
        print("正在转换凭证...")
        success_count = 0
        failed_count = 0
        skipped_count = 0
        skipped_accounts: List[Tuple[str, str, str]] = []
        exported_accounts: List[dict] = []  # 用于单文件模式收集凭证

        for actual_idx, account_summary in range_accounts:
            account_id = account_summary['id']
            email = account_summary['email']
            name = account_summary.get('name', '')

            try:
                # 加载账号详细数据
                if args.verbose:
                    print(f"\n[{actual_idx}] 处理账号: {email}")

                account = load_account(account_id)

                # 验证账号有效性
                is_valid, reason = validate_account(account)

                if not is_valid and not args.include_invalid:
                    # 跳过无效账号
                    skipped_count += 1
                    skipped_accounts.append((email, name, reason))
                    if args.verbose:
                        print(f"    ⏭️  跳过: {reason}")
                    continue

                # 转换为 Antigravity2api-nodejs 格式
                nodejs_cred = convert_to_nodejs_format(account)

                # 根据导出格式处理
                if export_format == 'single':
                    # 单文件模式：收集到列表中
                    exported_accounts.append(nodejs_cred)
                    success_count += 1
                    if args.verbose:
                        print(f"    ✓ 转换成功")
                    else:
                        print(f"  ✓ [{actual_idx}] {email}")
                else:
                    # 多文件模式：逐个导出
                    if args.dry_run:
                        safe_email = sanitize_filename(email)
                        filename = f"antigravity-{safe_email}.json"
                        if args.verbose:
                            print(f"    [试运行] 将导出: {filename}")
                        else:
                            print(f"  [试运行] [{actual_idx}] {email} → {filename}")
                        success_count += 1
                    else:
                        export_success, result = export_single_credential(nodejs_cred, args.output, email)
                        if export_success:
                            filename = Path(result).name
                            if args.verbose:
                                print(f"    ✓ 导出成功: {filename}")
                            else:
                                print(f"  ✓ [{actual_idx}] {email} → {filename}")
                            success_count += 1
                        else:
                            print(f"  ✗ [{actual_idx}] {email} - {result}")
                            failed_count += 1

            except Exception as e:
                error_msg = f"处理失败: {e}"
                print(f"  ✗ [{actual_idx}] {email} - {error_msg}")
                failed_count += 1

        # 8. 单文件模式：写入 accounts.json
        output_path = args.output
        if export_format == 'single' and exported_accounts:
            output_file = args.output / "accounts.json"
            if args.dry_run:
                print(f"\n[试运行] 将导出 {len(exported_accounts)} 个账号到: {output_file}")
            else:
                print(f"\n正在写入 accounts.json...")
                export_success, result = export_accounts_array(exported_accounts, output_file)
                if not export_success:
                    print(f"❌ {result}")
                    return 1
                print(f"✓ 已导出到: {output_file}")
            output_path = output_file

        # 9. 输出跳过账号的详细报告
        print_skipped_report(skipped_accounts)

        # 10. 打印摘要
        print_summary(success_count, failed_count, skipped_count, output_path, total_in_range, export_format)

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
