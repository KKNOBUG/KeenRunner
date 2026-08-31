#!/bin/bash
#
# Celery Worker / Beat 部署脚本
# 用法: ./celery_deploy.sh start|stop|restart|status ...
#

set -euo pipefail

# 脚本所在目录即 backend 根目录（勿再手写占位路径）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$SCRIPT_DIR}"

# 保证能 import backend.*
export PYTHONPATH="${PROJECT_ROOT}/..:${PYTHONPATH:-}"
cd "$PROJECT_ROOT" || exit 1

CELERY_APP="backend.celery_scheduler.celery_worker:celery"
CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
# 队列名与 celery_config.py 端口前缀隔离保持一致（{port}_default,{port}_autotest），从.env读取端口避免漂移
SERVER_PORT="$(grep -E '^SERVER_PORT=' .env 2>/dev/null | head -n1 | cut -d= -f2 | tr -d ' \r')"
SERVER_PORT="${SERVER_PORT:-8519}"
CELERY_WORKER_QUEUES="${CELERY_WORKER_QUEUES:-${SERVER_PORT}_default,${SERVER_PORT}_autotest}"
CELERY_BEAT_SCHEDULER="${CELERY_BEAT_SCHEDULER:-redbeat.schedulers:RedBeatScheduler}"
CELERY_LOG_DIR="${PROJECT_ROOT}/output/logs/celery_logs"
mkdir -p "$CELERY_LOG_DIR"
CELERY_WORKER_LOG="${CELERY_LOG_DIR}/celery_worker.log"
CELERY_BEAT_LOG="${CELERY_LOG_DIR}/celery_beat.log"
CELERY_WORKER_PID="${PROJECT_ROOT}/celery_worker.pid"
CELERY_BEAT_PID="${PROJECT_ROOT}/celery_beat.pid"

# 供 setup_logging / worker_process_init 在接管 logging 后仍能挂到同一文件
export CELERY_WORKER_LOGFILE="${CELERY_WORKER_LOG}"
export CELERY_BEAT_LOGFILE="${CELERY_BEAT_LOG}"

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

stop_process() {
    local pid_file=$1
    local process_name=$2

    if ! is_running "$pid_file"; then
        print_info "${process_name} 未运行(跳过)..."
        return 1
    fi

    local pid
    pid=$(cat "$pid_file")
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

    # --logfile 会传入 setup_logging(logfile=...)；同时导出环境变量供 fork 后重建 sink
    export CELERY_LOGFILE="${CELERY_WORKER_LOG}"
    celery -A "$CELERY_APP" worker \
        --loglevel=INFO \
        --concurrency="${CELERY_WORKER_CONCURRENCY}" \
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
        # 若自定义 logging 未生效，至少保证文件存在且可写
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
    stop_process "$CELERY_WORKER_PID" "Celery Worker"
}

stop_celery_beat() {
    stop_process "$CELERY_BEAT_PID" "Celery Beat"
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
            stop_celery_worker
            stop_celery_beat
            ;;
        restart)
            stop_celery_worker
            stop_celery_beat
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
            stop_celery_worker
            ;;
        start-beat)
            start_celery_beat
            ;;
        stop-beat)
            stop_celery_beat
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
            echo "提示: 自定义 logging 时必须由 setup_logging 接收 --logfile 并挂文件 sink"
            echo "==================== Celery 启动脚本说明 ===================="
            exit 1
            ;;
    esac
}

main "$@"
