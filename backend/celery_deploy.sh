#!/bin/bash
# Celery Worker / Beat 部署脚本
# 用法: ./celery_deploy.sh start|stop|restart|status ...
# 同机多实例: 各部署目录 .env 的 SERVER_PORT 错开；共用 Redis 时 CELERY_REDBEAT_DB 必须不同

set -euo pipefail

# 脚本所在目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 保证能 import backend.*（代码以 backend 包前缀导入，PYTHONPATH 须指向仓库根）
cd "$PROJECT_ROOT" || { echo "无法进入项目目录: $PROJECT_ROOT"; exit 1; }
export PYTHONPATH="${PROJECT_ROOT}/..${PYTHONPATH:+:${PYTHONPATH}}"

# 自动激活虚拟环境（已激活则跳过）
if [ -z "${VIRTUAL_ENV:-}" ] && [ -f "${PROJECT_ROOT}/.venv/bin/activate" ]; then
    # shellcheck disable=SC1091
    source "${PROJECT_ROOT}/.venv/bin/activate"
fi

# 服务端口从 .env 读取：PID/日志/进程名均以端口区分
SERVER_PORT="$(grep -E '^SERVER_PORT=' "${PROJECT_ROOT}/.env" 2>/dev/null | head -n1 | cut -d= -f2 | tr -d ' \r')"
if [ -z "$SERVER_PORT" ]; then
    echo "[ERROR] 环境配置文件 .env 缺少 SERVER_PORT 配置" >&2
    exit 1
fi

# 配置Celery服务
CELERY_APP="backend.celery_scheduler.celery_worker:celery"
CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
CELERY_WORKER_QUEUES="${CELERY_WORKER_QUEUES:-${SERVER_PORT}_default,${SERVER_PORT}_autotest,${SERVER_PORT}_perf}"
CELERY_BEAT_SCHEDULER="${CELERY_BEAT_SCHEDULER:-redbeat.schedulers:RedBeatScheduler}"
CELERY_LOG_DIR="${PROJECT_ROOT}/output/logs/celery_logs"
mkdir -p "$CELERY_LOG_DIR"
CELERY_WORKER_LOG="${CELERY_LOG_DIR}/Worker-${SERVER_PORT}.log"
CELERY_BEAT_LOG="${CELERY_LOG_DIR}/Beat-${SERVER_PORT}.log"
CELERY_WORKER_PID="${PROJECT_ROOT}/celery_worker_${SERVER_PORT}.pid"
CELERY_BEAT_PID="${PROJECT_ROOT}/celery_beat_${SERVER_PORT}.pid"

print_info() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

print_warn() {
    echo -e "\033[33m[WARN]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid
        pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    return 1
}

# 校验 PID 对应进程确为 Celery，防 PID 复用误杀无关进程
pid_is_service() {
    ps -p "$1" -o args= 2>/dev/null | grep -q "$2"
}

stop_process() {
    local pid_file=$1
    local process_name=$2
    local service_keyword=$3

    if ! is_running "$pid_file"; then
        print_info "${process_name} 未运行(跳过)..."
        return 1
    fi

    local pid
    pid=$(cat "$pid_file")

    if ! pid_is_service "$pid" "$service_keyword"; then
        print_warn "PID $pid 已被无关进程复用, 不执行终止, 仅清理过期PID文件"
        rm -f "$pid_file"
        return 1
    fi

    print_info "停止 ${process_name}(PID: $pid)..."

    kill -TERM "$pid" 2>/dev/null || true

    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        print_warn "${process_name} 未正常退出, 强制终止..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$pid_file"
    print_info "${process_name} 已停止..."
    return 0
}

start_celery_worker() {
    if is_running "$CELERY_WORKER_PID"; then
        local pid
        pid=$(cat "$CELERY_WORKER_PID")
        print_warn "Celery Worker 已在运行(PID: $pid)"
        return 1
    fi

    print_info "启动 Celery Worker (并发数: ${CELERY_WORKER_CONCURRENCY}, 队列: ${CELERY_WORKER_QUEUES})..."
    print_info "日志文件: ${CELERY_WORKER_LOG}"

    # --logfile 传入 setup_loggers；CELERY_LOGFILE 供 prefork 子进程重建 sink 时挂到同一文件
    export CELERY_LOGFILE="${CELERY_WORKER_LOG}"
    celery -A "$CELERY_APP" worker \
        --loglevel=INFO \
        --concurrency="${CELERY_WORKER_CONCURRENCY}" \
        --hostname="worker_${SERVER_PORT}@%h" \
        --queues="${CELERY_WORKER_QUEUES}" \
        --logfile="${CELERY_WORKER_LOG}" \
        --pidfile="${CELERY_WORKER_PID}" \
        --pool=solo \
        --detach

    sleep 3

    if is_running "$CELERY_WORKER_PID"; then
        local pid
        pid=$(cat "$CELERY_WORKER_PID")
        print_info "Celery Worker 启动成功(PID: $pid)"
        print_info "日志文件: $CELERY_WORKER_LOG"
        touch "$CELERY_WORKER_LOG" 2>/dev/null || true
        return 0
    else
        print_error "Celery Worker 启动失败, 请查看日志: $CELERY_WORKER_LOG"
        if [ -f "$CELERY_WORKER_LOG" ]; then
            print_error "----- 最近日志 -----"
            tail -n 40 "$CELERY_WORKER_LOG" || true
        fi
        return 1
    fi
}

start_celery_beat() {
    if is_running "$CELERY_BEAT_PID"; then
        local pid
        pid=$(cat "$CELERY_BEAT_PID")
        print_warn "Celery Beat 已在运行(PID: $pid)"
        return 1
    fi

    print_info "启动 Celery Beat (调度器: ${CELERY_BEAT_SCHEDULER})..."
    print_info "日志文件: ${CELERY_BEAT_LOG}"

    export CELERY_LOGFILE="${CELERY_BEAT_LOG}"
    celery -A "$CELERY_APP" beat \
        --loglevel=INFO \
        --scheduler="${CELERY_BEAT_SCHEDULER}" \
        --logfile="${CELERY_BEAT_LOG}" \
        --pidfile="${CELERY_BEAT_PID}" \
        --detach

    sleep 3

    if is_running "$CELERY_BEAT_PID"; then
        local pid
        pid=$(cat "$CELERY_BEAT_PID")
        print_info "Celery Beat 启动成功(PID: $pid)"
        print_info "日志文件: $CELERY_BEAT_LOG"
        touch "$CELERY_BEAT_LOG" 2>/dev/null || true
        return 0
    else
        print_error "Celery Beat 启动失败, 请查看日志: $CELERY_BEAT_LOG"
        if [ -f "$CELERY_BEAT_LOG" ]; then
            print_error "----- 最近日志 -----"
            tail -n 40 "$CELERY_BEAT_LOG" || true
        fi
        return 1
    fi
}

stop_celery_worker() {
    stop_process "$CELERY_WORKER_PID" "Celery Worker" "celery"
}

stop_celery_beat() {
    stop_process "$CELERY_BEAT_PID" "Celery Beat" "celery"
}

celery_status() {
    echo "========== Celery 进程状态 =========="
    echo "PROJECT_ROOT: $PROJECT_ROOT"
    echo "PYTHONPATH:   $PYTHONPATH"

    if is_running "$CELERY_WORKER_PID"; then
        local pid
        pid=$(cat "$CELERY_WORKER_PID")
        echo "[✓] Celery Worker: 运行中(PID: $pid)"
    else
        echo "[×] Celery Worker: 未运行"
    fi

    if is_running "$CELERY_BEAT_PID"; then
        local pid
        pid=$(cat "$CELERY_BEAT_PID")
        echo "[✓] Celery Beat: 运行中(PID: $pid)"
    else
        echo "[×] Celery Beat: 未运行"
    fi

    echo ""
    echo "日志文件:"
    echo "  Worker: $CELERY_WORKER_LOG$([ -f "$CELERY_WORKER_LOG" ] && echo " (存在)" || echo " (尚不存在)")"
    echo "  Beat:   $CELERY_BEAT_LOG$([ -f "$CELERY_BEAT_LOG" ] && echo " (存在)" || echo " (尚不存在)")"
    echo "========== Celery 进程状态 =========="
}

main() {
    case "${1:-}" in
        start)
            if [ -n "${2:-}" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            start_celery_worker
            start_celery_beat
            ;;
        stop)
            # 未运行返回非零，|| true 避免 set -e 中断后续停止
            stop_celery_worker || true
            stop_celery_beat || true
            ;;
        restart)
            stop_celery_worker || true
            stop_celery_beat || true
            sleep 2
            if [ -n "${2:-}" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            start_celery_worker
            start_celery_beat
            ;;
        status)
            celery_status
            ;;
        start-worker)
            if [ -n "${2:-}" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            start_celery_worker
            ;;
        stop-worker)
            stop_celery_worker || true
            ;;
        start-beat)
            start_celery_beat
            ;;
        stop-beat)
            stop_celery_beat || true
            ;;
        *)
            echo "==================== Celery 启动脚本说明 ===================="
            echo ""
            echo "命令说明:"
            echo "  start [并发数]         # 启动 Worker + Beat"
            echo "  stop                  # 停止 Worker + Beat"
            echo "  restart [并发数]       # 重启"
            echo "  status                # 查看状态"
            echo "  start-worker [并发数]  # 仅启动 Worker"
            echo "  stop-worker           # 仅停止 Worker"
            echo "  start-beat            # 仅启动 Beat"
            echo "  stop-beat             # 仅停止 Beat"
            echo ""
            echo "日志目录: $CELERY_LOG_DIR"
            echo "提示: 自定义 logging 时必须由 setup_loggers 接收 --logfile 并挂文件 sink"
            echo "==================== Celery 启动脚本说明 ===================="
            exit 1
            ;;
    esac
}

main "$@"
