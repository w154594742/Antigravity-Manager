#!/usr/bin/env bash
#
# CLIProxyAPI 授权文件分发上传脚本
#
# 将本地导出的授权文件按指定份数均分，上传到阿里云服务器对应的
# CLIProxyAPI 实例目录中，并重启相关服务。
#
# 使用方法:
#   bash scripts/upload-to-cliproxyapi.sh              # 交互模式
#   bash scripts/upload-to-cliproxyapi.sh -n 3         # 指定分割为3份
#   bash scripts/upload-to-cliproxyapi.sh -s ~/mydir   # 指定源目录
#   bash scripts/upload-to-cliproxyapi.sh -n 2 -s ~/mydir
#
# @author wangqiupei

set -euo pipefail

# ============================================================
# 配置常量
# ============================================================

# 服务器连接信息
REMOTE_HOST="8.137.115.72"
REMOTE_USER="root"
REMOTE_PASS="Admin2012,."
REMOTE_PORT="22"

# 远程项目基础路径
REMOTE_BASE="/opt/docker_projects"

# 4个 CLIProxyAPI 实例目录名（按顺序）
REMOTE_DIRS=("CLIProxyAPI" "CLIProxyAPI-2" "CLIProxyAPI-3" "CLIProxyAPI-4")

# 默认本地源目录
DEFAULT_SOURCE_DIR="$HOME/Downloads/cliproxyapi"

# 备份保留数量
BACKUP_KEEP_COUNT=3

# SSH/SCP 公共选项
SSH_OPTS="-o StrictHostKeyChecking=no -o ConnectTimeout=10"

# ============================================================
# 工具函数
# ============================================================

# 在远程服务器执行命令
remote_exec() {
    sshpass -p "$REMOTE_PASS" ssh $SSH_OPTS -p "$REMOTE_PORT" \
        "${REMOTE_USER}@${REMOTE_HOST}" "$1"
}

# 上传文件到远程服务器指定目录
remote_upload() {
    local remote_dir="$1"
    shift
    # 接收文件列表作为剩余参数
    sshpass -p "$REMOTE_PASS" scp $SSH_OPTS -P "$REMOTE_PORT" \
        "$@" "${REMOTE_USER}@${REMOTE_HOST}:${remote_dir}/"
}

# 输出带颜色的信息
info()    { echo -e "\033[34m[INFO]\033[0m $*"; }
success() { echo -e "\033[32m[OK]\033[0m $*"; }
warn()    { echo -e "\033[33m[WARN]\033[0m $*"; }
error()   { echo -e "\033[31m[ERROR]\033[0m $*" >&2; }

# ============================================================
# 核心函数
# ============================================================

# 预检查：确认必要条件
check_prerequisites() {
    info "执行预检查..."

    # 检查 sshpass
    if ! command -v sshpass &>/dev/null; then
        error "未安装 sshpass，请先安装: brew install sshpass 或 apt install sshpass"
        exit 1
    fi

    # 检查源目录
    if [[ ! -d "$SOURCE_DIR" ]]; then
        error "源目录不存在: $SOURCE_DIR"
        exit 1
    fi

    # 统计 json 文件数
    FILE_COUNT=$(find "$SOURCE_DIR" -maxdepth 1 -name "*.json" -type f | wc -l | tr -d ' ')
    if [[ "$FILE_COUNT" -eq 0 ]]; then
        error "源目录中没有 json 文件: $SOURCE_DIR"
        exit 1
    fi

    # 测试服务器连接
    if ! remote_exec "echo ok" &>/dev/null; then
        error "无法连接服务器 $REMOTE_HOST"
        exit 1
    fi

    success "预检查通过（本地 $FILE_COUNT 个授权文件，服务器连接正常）"
}

# 交互选择分割份数
select_split_count() {
    # 如果已通过参数指定，直接验证
    if [[ -n "${SPLIT_COUNT:-}" ]]; then
        if [[ "$SPLIT_COUNT" -ge 1 && "$SPLIT_COUNT" -le 4 ]]; then
            return
        else
            error "分割数必须在 1~4 之间，当前值: $SPLIT_COUNT"
            exit 1
        fi
    fi

    echo ""
    echo "=========================================="
    echo " 本地授权文件: $FILE_COUNT 个"
    echo "=========================================="
    echo " 请选择分割方式:"
    echo "   1) 全部上传到 CLIProxyAPI（$FILE_COUNT 个）"

    # 动态计算每种分割方式的分配情况
    for n in 2 3 4; do
        local base=$((FILE_COUNT / n))
        local remainder=$((FILE_COUNT % n))
        local desc=""
        for ((i = 0; i < n; i++)); do
            local cnt=$base
            if [[ $i -lt $remainder ]]; then
                cnt=$((base + 1))
            fi
            if [[ -n "$desc" ]]; then
                desc="$desc / $cnt"
            else
                desc="$cnt"
            fi
        done
        echo "   $n) 均分到前 ${n} 个目录（$desc 个）"
    done
    echo "=========================================="

    while true; do
        read -rp "请输入选择 [1-4]: " SPLIT_COUNT
        if [[ "$SPLIT_COUNT" =~ ^[1-4]$ ]]; then
            break
        fi
        warn "无效输入，请输入 1~4 之间的数字"
    done
}

# 备份远程 auths 目录并清理旧备份
backup_and_cleanup() {
    local count="$1"
    info "备份选中的 $count 个目录的授权文件..."

    local timestamp
    timestamp=$(remote_exec "date +'%Y%m%d_%H%M%S'")

    for ((i = 0; i < count; i++)); do
        local dir_name="${REMOTE_DIRS[$i]}"
        local remote_path="${REMOTE_BASE}/${dir_name}"

        # 备份
        remote_exec "cd '$remote_path' && tar czf 'auths_backup_${timestamp}.tar.gz' auths/ 2>/dev/null" || true

        # 清理旧备份，只保留最新 N 个
        remote_exec "cd '$remote_path' && ls -1t auths_backup_*.tar.gz 2>/dev/null | tail -n +$((BACKUP_KEEP_COUNT + 1)) | xargs -r rm -f"

        success "  ${dir_name}: 备份完成，已清理旧备份（保留最新 $BACKUP_KEEP_COUNT 个）"
    done
}

# 清空远程 auths 目录中的 json 文件
clear_remote_auths() {
    local count="$1"
    info "清空选中的 $count 个目录的授权文件..."

    for ((i = 0; i < count; i++)); do
        local dir_name="${REMOTE_DIRS[$i]}"
        remote_exec "rm -f '${REMOTE_BASE}/${dir_name}/auths/'*.json"
        success "  ${dir_name}/auths: 已清空"
    done
}

# 将文件分组并上传
split_and_upload() {
    local count="$1"
    info "分组上传文件（分 $count 份）..."

    # 生成排序后的文件列表
    local files=()
    while IFS= read -r f; do
        files+=("$f")
    done < <(find "$SOURCE_DIR" -maxdepth 1 -name "*.json" -type f | sort)

    local total=${#files[@]}
    local base=$((total / count))
    local remainder=$((total % count))
    local idx=0

    for ((i = 0; i < count; i++)); do
        local dir_name="${REMOTE_DIRS[$i]}"
        local remote_path="${REMOTE_BASE}/${dir_name}/auths"

        # 计算当前组的文件数（余数优先分配给前面的组）
        local group_size=$base
        if [[ $i -lt $remainder ]]; then
            group_size=$((base + 1))
        fi

        # 提取当前组的文件
        local group=("${files[@]:$idx:$group_size}")

        # 上传
        remote_upload "$remote_path" "${group[@]}"
        success "  ${dir_name}/auths: 上传 $group_size 个文件"

        idx=$((idx + group_size))
    done
}

# 停止 docker compose 服务
stop_services() {
    local count="$1"
    info "停止选中的 $count 个服务..."

    for ((i = 0; i < count; i++)); do
        local dir_name="${REMOTE_DIRS[$i]}"
        local remote_path="${REMOTE_BASE}/${dir_name}"

        remote_exec "cd '$remote_path' && docker compose down" 2>/dev/null
        success "  ${dir_name}: 已停止"
    done
}

# 启动 docker compose 服务
start_services() {
    local count="$1"
    info "启动选中的 $count 个服务..."

    for ((i = 0; i < count; i++)); do
        local dir_name="${REMOTE_DIRS[$i]}"
        local remote_path="${REMOTE_BASE}/${dir_name}"

        remote_exec "cd '$remote_path' && docker compose up -d" 2>/dev/null
        success "  ${dir_name}: docker compose up -d 完成"
    done
}

# 验证上传结果
verify_result() {
    local count="$1"
    echo ""
    echo "=========================================="
    echo " 验证结果"
    echo "=========================================="

    local total_remote=0
    for ((i = 0; i < count; i++)); do
        local dir_name="${REMOTE_DIRS[$i]}"
        local remote_count
        remote_count=$(remote_exec "ls '${REMOTE_BASE}/${dir_name}/auths/'*.json 2>/dev/null | wc -l" | tr -d ' ')
        echo "  ${dir_name}/auths: ${remote_count} 个文件"
        total_remote=$((total_remote + remote_count))
    done

    echo "------------------------------------------"
    echo "  本地文件总数: $FILE_COUNT"
    echo "  远程文件总数: $total_remote"

    if [[ "$total_remote" -eq "$FILE_COUNT" ]]; then
        success "验证通过！文件数量一致"
    else
        warn "文件数量不一致，请检查"
    fi
    echo "=========================================="
}

# ============================================================
# 参数解析
# ============================================================

SOURCE_DIR="$DEFAULT_SOURCE_DIR"
SPLIT_COUNT=""
FILE_COUNT=0

while getopts "n:s:h" opt; do
    case $opt in
        n) SPLIT_COUNT="$OPTARG" ;;
        s) SOURCE_DIR="$OPTARG" ;;
        h)
            echo "用法: $0 [-n 分割数(1~4)] [-s 源目录]"
            echo ""
            echo "选项:"
            echo "  -n  指定分割份数（1~4），不指定则交互选择"
            echo "  -s  指定源目录，默认为 $DEFAULT_SOURCE_DIR"
            echo "  -h  显示帮助信息"
            exit 0
            ;;
        *) exit 1 ;;
    esac
done

# ============================================================
# 主流程
# ============================================================

main() {
    echo ""
    echo "================================================"
    echo " CLIProxyAPI 授权文件分发上传工具"
    echo "================================================"
    echo ""

    # 1. 预检查
    check_prerequisites

    # 2. 交互选择分割份数
    select_split_count
    echo ""
    info "选择: 分割为 $SPLIT_COUNT 份，上传到前 $SPLIT_COUNT 个目录"
    echo ""

    # 3. 备份 + 清理旧备份
    backup_and_cleanup "$SPLIT_COUNT"
    echo ""

    # 4. 停止服务（防止运行中的服务写入 auths 目录干扰上传）
    stop_services "$SPLIT_COUNT"
    echo ""

    # 5. 清空远程 auths
    clear_remote_auths "$SPLIT_COUNT"
    echo ""

    # 6. 分组上传
    split_and_upload "$SPLIT_COUNT"
    echo ""

    # 7. 验证上传结果
    verify_result "$SPLIT_COUNT"
    echo ""

    # 8. 启动服务
    start_services "$SPLIT_COUNT"

    echo ""
    success "全部完成！"
}

main
