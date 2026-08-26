#!/bin/bash
# -*- coding: utf-8 -*-
# 适配: Kylin Linux Advanced Server V10 (Tercel), x86_64, 8核QEMU虚拟CPU
# 用法: ./deploy.sh <command> [options]

set -euo pipefail

# ==================== 自动定位项目根目录 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR}"
cd "$PROJECT_ROOT" || { echo "无法进入项目目录: $PROJECT_ROOT"; exit 1; }

# ==================== 环境检测与适配 ====================
CPU_CORES=$(nproc 2>/dev/null || echo "4")
GUNICORN_WORKERS=$((CPU_CORES * 2 + 1))
[ "$GUNICORN_WORKERS" -gt 8 ] && GUNICORN_WORKERS=8
CELERY_DEFAULT_CONCURRENCY=$CPU_CORES

# ==================== 路径配置 ====================
VENV_PATH="${PROJECT_ROOT}/.venv"
PYTHON_BIN="${VENV_PATH}/bin/python"
CELERY_BIN="${VENV_PATH}/bin/celery"
GUNICORN_BIN="${VENV_PATH}/bin/gunicorn"

# 日志目录
LOG_DIR="${PROJECT_ROOT}/output/logs"
CELERY_LOG_DIR="${LOG_DIR}/celery_logs"
mkdir -p "$CELERY_LOG_DIR"

# PID 文件
GUNICORN_PID_FILE="${PROJECT_ROOT}/gunicorn.pid"
CELERY_WORKER_PID_FILE="${PROJECT_ROOT}/celery_worker.pid"
CELERY_BEAT_PID_FILE="${PROJECT_ROOT}/celery_beat.pid"

# 日志文件
FASTAPI_LOG_FILE="${PROJECT_ROOT}/backend_main.log"
CELERY_WORKER_LOG="${CELERY_LOG_DIR}/celery_worker.log"
CELERY_BEAT_LOG="${CELERY_LOG_DIR}/celery_beat.log"

# ==================== 应用配置 ====================
GUNICORN_APP="backend_main:app"
GUNICORN_CONFIG_FILE="${PROJECT_ROOT}/gunicorn.conf.py"
CELERY_APP="backend.celery_scheduler.celery_worker:celery"
CELERY_WORKER_POOL="solo"
CELERY_WORKER_QUEUES="default,autotest_queue"
CELERY_BEAT_SCHEDULER="redbeat.schedulers:RedBeatScheduler"
CELERY_WORKER_PREFETCH_MULTIPLIER=1
CELERY_WORKER_MAX_TASKS_PER_CHILD=200

# Git 配置
GIT_BRANCH="${GIT_BRANCH:-}"
GIT_USERNAME="${GIT_USERNAME:-}"
GIT_PASSWORD="${GIT_PASSWORD:-}"

# ==================== 日志函数 ====================
print_info()  { echo -e "\033[32m[INFO]\033[0m  $(date '+%Y-%m-%d %H:%M:%S') $1"; }
print_warn()  { echo -e "\033[33m[WARN]\033[0m  $(date '+%Y-%m-%d %H:%M:%S') $1"; }
print_error() { echo -e "\033[31m[ERROR]\033[0m $(date '+%Y-%m-%d %H:%M:%S') $1"; }
print_step()  { echo -e "\n\033[36m========== $1 ==========\033[0m"; }

# ==================== 工具函数 ====================
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "命令未安装: $1"
        return 1
    fi
    return 0
}

check_venv() {
    if [ ! -f "$PYTHON_BIN" ]; then
        print_error "虚拟环境不存在: $VENV_PATH"
        print_info "请先创建虚拟环境: python3 -m venv .venv"
        return 1
    fi
    return 0
}

# 激活虚拟环境
activate_venv() {
    if [ -f "${VENV_PATH}/bin/activate" ]; then
        source "${VENV_PATH}/bin/activate"
        print_info "虚拟环境已激活: $VENV_PATH"
    else
        print_error "虚拟环境激活脚本不存在: ${VENV_PATH}/bin/activate"
        return 1
    fi
}

# 检查进程是否运行（通过 PID 文件）
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file" 2>/dev/null)
        if [ -n "$pid" ] && ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    return 1
}

# 通过进程名查找 PID
find_pid_by_name() {
    local pattern=$1
    pgrep -f "$pattern" 2>/dev/null || true
}

# 强制清理进程（精确匹配当前项目）
force_kill() {
    local pattern=$1
    local name=$2
    local pids
    
    # 查找匹配进程，并验证工作目录是否为当前项目
    pids=$(pgrep -f "$pattern" 2>/dev/null | while read -r pid; do
        # 获取进程的工作目录
        local cwd
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || echo "")
        # 只返回当前项目目录下的进程
        if [ "$cwd" = "$PROJECT_ROOT" ]; then
            echo "$pid"
        fi
    done)
    
    if [ -n "$pids" ]; then
        print_warn "强制终止 ${name}: $pids"
        echo "$pids" | xargs -r kill -9 2>/dev/null || true
        sleep 1
    else
        print_info "${name} 无残留进程"
    fi
}

# 停止进程（优雅 -> 强制）
stop_process() {
    local pid_file=$1
    local process_name=$2
    local timeout=${3:-10}

    if ! is_running "$pid_file"; then
        print_info "${process_name} 未运行"
        return 0
    fi

    local pid
    pid=$(cat "$pid_file")
    print_info "停止 ${process_name} (PID: $pid)..."

    # 发送 TERM 信号
    kill -TERM "$pid" 2>/dev/null || true

    # 等待进程退出
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt $timeout ]; do
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo ""

    # 强制终止
    if ps -p "$pid" > /dev/null 2>&1; then
        print_warn "${process_name} 未响应 TERM，发送 KILL..."
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi

    # 清理 PID 文件
    rm -f "$pid_file"

    # 验证
    if ps -p "$pid" > /dev/null 2>&1; then
        print_error "${process_name} 停止失败"
        return 1
    else
        print_info "${process_name} 已停止"
        return 0
    fi
}

# ==================== FastAPI 服务控制 ====================
fastapi_start() {
    print_step "启动 FastAPI 服务"

    if is_running "$GUNICORN_PID_FILE"; then
        local pid
        pid=$(cat "$GUNICORN_PID_FILE")
        print_warn "FastAPI 已在运行 (PID: $pid)"
        return 0
    fi

    check_venv || return 1
    activate_venv || return 1
    check_command "$GUNICORN_BIN" || { print_error "gunicorn 未安装"; return 1; }

    if [ ! -f "$GUNICORN_CONFIG_FILE" ]; then
        print_error "Gunicorn 配置文件不存在: $GUNICORN_CONFIG_FILE"
        return 1
    fi

    print_info "Workers: $GUNICORN_WORKERS, 配置: $GUNICORN_CONFIG_FILE"
    print_info "日志: $FASTAPI_LOG_FILE"

    nohup "$GUNICORN_BIN" -c "$GUNICORN_CONFIG_FILE" "$GUNICORN_APP" \
        >> "$FASTAPI_LOG_FILE" 2>&1 &

    # 记录 PID
    local gunicorn_pid=$!
    echo "$gunicorn_pid" > "$GUNICORN_PID_FILE"
    print_info "Gunicorn 主进程 PID: $gunicorn_pid"

    # 等待启动
    local count=0
    while [ $count -lt 15 ]; do
        if is_running "$GUNICORN_PID_FILE"; then
            print_info "FastAPI 启动成功 (PID: $gunicorn_pid)"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    print_error "FastAPI 启动失败，查看日志: tail -n 50 $FASTAPI_LOG_FILE"
    return 1
}

fastapi_stop() {
    print_step "停止 FastAPI 服务"

    # 先通过 PID 文件停止
    stop_process "$GUNICORN_PID_FILE" "FastAPI" 15

    # 强制清理残留
    force_kill "backend_main:app" "Gunicorn"
}

fastapi_restart() {
    print_step "重启 FastAPI 服务"
    fastapi_stop
    sleep 2
    fastapi_start
}

fastapi_status() {
    print_step "FastAPI 服务状态"
    echo "项目路径: $PROJECT_ROOT"
    echo "配置文件: $GUNICORN_CONFIG_FILE"
    echo "PID 文件: $GUNICORN_PID_FILE"
    echo "日志文件: $FASTAPI_LOG_FILE"
    echo ""

    # 检查进程（精确匹配当前项目）
    local gunicorn_pids
    gunicorn_pids=$(pgrep -f "gunicorn.*backend_main" 2>/dev/null | while read -r pid; do
        local cwd
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || echo "")
        if [ "$cwd" = "$PROJECT_ROOT" ]; then
            echo "$pid"
        fi
    done)

    if [ -n "$gunicorn_pids" ]; then
        print_info "[✓] FastAPI: 运行中"
        echo "    进程列表:"
        ps aux | grep -E "gunicorn.*backend_main" | grep -v grep | while read -r line; do
            echo "      $line"
        done
    else
        print_warn "[×] FastAPI: 未运行"
    fi

    # 显示日志文件状态
    if [ -f "$FASTAPI_LOG_FILE" ]; then
        local size
        size=$(du -h "$FASTAPI_LOG_FILE" 2>/dev/null | cut -f1)
        echo ""
        echo "    日志大小: $size"
    fi
}

fastapi_pull() {
    print_step "拉取最新代码"

    check_command "git" || return 1
    check_command "expect" || { print_error "expect 未安装，请先安装: yum install expect"; return 1; }

    if [ -z "$GIT_USERNAME" ] || [ -z "$GIT_PASSWORD" ]; then
        print_error "GIT_USERNAME 或 GIT_PASSWORD 未设置"
        print_info "用法: GIT_USERNAME=xxx GIT_PASSWORD=xxx $0 fastapi_pull"
        return 1
    fi

    print_info "分支: $GIT_BRANCH"

    # 使用 expect 交互式拉取代码
    print_info "正在拉取代码..."
    expect <<EOF
set timeout 30
spawn git fetch origin
expect {
    "Username" {
        send "${GIT_USERNAME}\r"
        exp_continue
    }
    "Password" {
        send "${GIT_PASSWORD}\r"
        exp_continue
    }
    eof
}
EOF

    if [ $? -ne 0 ]; then
        print_error "Git fetch 失败"
        return 1
    fi

    # 强制覆盖本地更改
    print_info "强制覆盖本地更改..."
    git reset --hard "origin/$GIT_BRANCH"

    if [ $? -ne 0 ]; then
        print_error "Git reset 失败"
        return 1
    fi

    print_info "代码拉取完成"
}

# ==================== Celery 服务控制 ====================
celery_start() {
    local concurrency=${1:-$CELERY_DEFAULT_CONCURRENCY}
    print_step "启动 Celery 服务 (并发: $concurrency)"
    celery_start_worker "$concurrency"
    celery_start_beat
}

celery_start_worker() {
    local concurrency=${1:-$CELERY_DEFAULT_CONCURRENCY}
    print_info "启动 Celery Worker (并发: $concurrency, 队列: $CELERY_WORKER_QUEUES)..."

    if is_running "$CELERY_WORKER_PID_FILE"; then
        local pid
        pid=$(cat "$CELERY_WORKER_PID_FILE")
        print_warn "Celery Worker 已在运行 (PID: $pid)"
        return 0
    fi

    check_venv || return 1
    activate_venv || return 1
    check_command "$CELERY_BIN" || { print_error "celery 未安装"; return 1; }

    export CELERY_LOGFILE="$CELERY_WORKER_LOG"
    export CELERY_WORKER_LOGFILE="$CELERY_WORKER_LOG"

    # 后台启动
    nohup "$CELERY_BIN" -A "$CELERY_APP" worker \
        --loglevel="INFO" \
        --concurrency="$concurrency" \
        --prefetch-multiplier="$CELERY_WORKER_PREFETCH_MULTIPLIER" \
        --max-tasks-per-child="$CELERY_WORKER_MAX_TASKS_PER_CHILD" \
        --queues="$CELERY_WORKER_QUEUES" \
        --logfile="$CELERY_WORKER_LOG" \
        --pidfile="$CELERY_WORKER_PID_FILE" \
        --pool="$CELERY_WORKER_POOL" \
        >> "$CELERY_WORKER_LOG" 2>&1 &

    local worker_pid=$!
    echo "$worker_pid" > "$CELERY_WORKER_PID_FILE"

    local count=0
    while [ $count -lt 10 ]; do
        if is_running "$CELERY_WORKER_PID_FILE"; then
            print_info "Celery Worker 启动成功 (PID: $worker_pid)"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    print_error "Celery Worker 启动失败，查看日志: tail -n 50 $CELERY_WORKER_LOG"
    return 1
}

celery_start_beat() {
    print_info "启动 Celery Beat (调度器: $CELERY_BEAT_SCHEDULER)..."

    if is_running "$CELERY_BEAT_PID_FILE"; then
        local pid
        pid=$(cat "$CELERY_BEAT_PID_FILE")
        print_warn "Celery Beat 已在运行 (PID: $pid)"
        return 0
    fi

    check_venv || return 1
    activate_venv || return 1
    check_command "$CELERY_BIN" || { print_error "celery 未安装"; return 1; }

    export CELERY_LOGFILE="$CELERY_BEAT_LOG"
    export CELERY_BEAT_LOGFILE="$CELERY_BEAT_LOG"

    nohup "$CELERY_BIN" -A "$CELERY_APP" beat \
        --loglevel="INFO" \
        --scheduler="$CELERY_BEAT_SCHEDULER" \
        --logfile="$CELERY_BEAT_LOG" \
        --pidfile="$CELERY_BEAT_PID_FILE" \
        >> "$CELERY_BEAT_LOG" 2>&1 &

    local beat_pid=$!
    echo "$beat_pid" > "$CELERY_BEAT_PID_FILE"

    local count=0
    while [ $count -lt 10 ]; do
        if is_running "$CELERY_BEAT_PID_FILE"; then
            print_info "Celery Beat 启动成功 (PID: $beat_pid)"
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done

    print_error "Celery Beat 启动失败，查看日志: tail -n 50 $CELERY_BEAT_LOG"
    return 1
}

celery_stop() {
    print_step "停止 Celery 服务"
    celery_stop_beat
    celery_stop_worker
}

celery_stop_worker() {
    stop_process "$CELERY_WORKER_PID_FILE" "Celery Worker" 15
    force_kill "celery.*worker" "Celery Worker"
}

celery_stop_beat() {
    stop_process "$CELERY_BEAT_PID_FILE" "Celery Beat" 10
    force_kill "celery.*beat" "Celery Beat"
}

celery_restart() {
    local concurrency=${1:-$CELERY_DEFAULT_CONCURRENCY}
    print_step "重启 Celery 服务 (并发: $concurrency)"
    celery_stop
    sleep 2
    celery_start "$concurrency"
}

celery_status() {
    print_step "Celery 服务状态"
    echo "项目路径: $PROJECT_ROOT"
    echo "日志目录: $CELERY_LOG_DIR"
    echo ""

    # 检查进程（精确匹配当前项目）
    local worker_pids
    worker_pids=$(pgrep -f "celery.*worker" 2>/dev/null | while read -r pid; do
        local cwd
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || echo "")
        if [ "$cwd" = "$PROJECT_ROOT" ]; then
            echo "$pid"
        fi
    done)
    local beat_pids
    beat_pids=$(pgrep -f "celery.*beat" 2>/dev/null | while read -r pid; do
        local cwd
        cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || echo "")
        if [ "$cwd" = "$PROJECT_ROOT" ]; then
            echo "$pid"
        fi
    done)

    if [ -n "$worker_pids" ]; then
        print_info "[✓] Celery Worker: 运行中"
        ps aux | grep -E "celery.*worker" | grep -v grep | while read -r line; do
            echo "      $line"
        done
    else
        print_warn "[×] Celery Worker: 未运行"
    fi

    echo ""

    if [ -n "$beat_pids" ]; then
        print_info "[✓] Celery Beat:  运行中"
        ps aux | grep -E "celery.*beat" | grep -v grep | while read -r line; do
            echo "      $line"
        done
    else
        print_warn "[×] Celery Beat:  未运行"
    fi

    echo ""
    echo "日志文件:"
    for log in "$CELERY_WORKER_LOG" "$CELERY_BEAT_LOG"; do
        if [ -f "$log" ]; then
            local size
            size=$(du -h "$log" 2>/dev/null | cut -f1)
            echo "  $(basename "$log"): $size"
        else
            echo "  $(basename "$log"): 不存在"
        fi
    done
}

# ==================== 全流程部署 ====================
full_deploy() {
    print_step "完整部署流程"
    print_info "项目路径: $PROJECT_ROOT"
    print_info "CPU 核心: $CPU_CORES"
    print_info "Gunicorn Workers: $GUNICORN_WORKERS"
    print_info "Celery 并发: $CELERY_DEFAULT_CONCURRENCY"
    echo ""

    # 1. 停止服务
    fastapi_stop
    celery_stop
    sleep 2

    # 2. 拉取代码
    fastapi_pull

    # 3. 启动 Celery
    celery_start "$CELERY_DEFAULT_CONCURRENCY"

    # 4. 启动 FastAPI
    fastapi_start

    # 5. 检查状态
    echo ""
    fastapi_status
    echo ""
    celery_status

    print_step "部署完成"
}

# ==================== 帮助信息 ====================
show_help() {
    cat << EOF
==================== ForkRunner 部署脚本 ====================
适配: Kylin Linux V10, x86_64, ${CPU_CORES}核CPU

用法: $0 <command> [options]

FastAPI 服务:
  fastapi_start              启动 FastAPI 服务
  fastapi_stop               停止 FastAPI 服务
  fastapi_restart            重启 FastAPI 服务
  fastapi_status             查看 FastAPI 状态
  fastapi_pull               拉取最新代码 (需 GIT_USERNAME/GIT_PASSWORD)

Celery 服务:
  celery_start [并发数]       启动 Worker + Beat (默认并发: $CELERY_DEFAULT_CONCURRENCY)
  celery_start_worker [并发数] 仅启动 Worker
  celery_start_beat          仅启动 Beat
  celery_stop                停止 Worker + Beat
  celery_stop_worker         仅停止 Worker
  celery_stop_beat           仅停止 Beat
  celery_restart [并发数]     重启 Worker + Beat
  celery_status              查看 Celery 状态

全流程:
  full_deploy                完整部署 (停止 -> 拉取 -> 启动)

环境变量:
  GIT_BRANCH                 Git 分支 (默认: master)
  GIT_USERNAME               Git 用户名
  GIT_PASSWORD               Git 密码

依赖工具:
  expect                     Git 交互式认证必需 (yum install expect)

示例:
  $0 fastapi_start
  $0 celery_start 4
  GIT_USERNAME=user GIT_PASSWORD=pass $0 fastapi_pull
  GIT_USERNAME=user GIT_PASSWORD=pass $0 full_deploy

日志位置:
  FastAPI: $FASTAPI_LOG_FILE
  Celery:  $CELERY_LOG_DIR/
==================== ForkRunner 部署脚本 ====================
EOF
}

# ==================== 主入口 ====================
main() {
    case "${1:-}" in
        fastapi_start)    fastapi_start ;;
        fastapi_stop)     fastapi_stop ;;
        fastapi_restart)  fastapi_restart ;;
        fastapi_status)   fastapi_status ;;
        fastapi_pull)     fastapi_pull ;;

        celery_start)        celery_start "${2:-}" ;;
        celery_start_worker) celery_start_worker "${2:-}" ;;
        celery_start_beat)   celery_start_beat ;;
        celery_stop)         celery_stop ;;
        celery_stop_worker)  celery_stop_worker ;;
        celery_stop_beat)    celery_stop_beat ;;
        celery_restart)      celery_restart "${2:-}" ;;
        celery_status)       celery_status ;;

        full_deploy)      full_deploy ;;

        help|--help|-h|"") show_help ;;

        *)
            print_error "未知命令: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"