#!/bin/bash

# 配置脚本所在目录
PROJECT_ROOT="服务器上的后端项目所在目录"

# 配置Celery服务
CELERY_APP="celery_scheduler.celery_worker:celery"
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_QUEUES="autotest_queue,default"
CELERY_BEAT_SCHEDULER="redbeat.schedulers:RedBeatScheduler"
CELERY_LOG_DIR="${PROJECT_ROOT}/output/logs/celery_logs"
mkdir -p "$CELERY_LOG_DIR"
CELERY_WORKER_LOG="${CELERY_LOG_DIR}/celery_worker.log"
CELERY_BEAT_LOG="${CELERY_LOG_DIR}/celery_beat.log"
CELERY_WORKER_PID="${PROJECT_ROOT}/celery_worker.pid"
CELERY_BEAT_PID="${PROJECT_ROOT}/celery_beat.pid"


print_info() {
    echo -e "\033[32m[INFO]\033[0m $1"
}

print_warn() {
    echo -e "\033[33m[WARN]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

print_step() {
    echo -e "\n"
    echo -e "\033[36m========================================\033[0m"
    echo -e "\033[36m$1\033[0m"
    echo -e "\033[36m========================================\033[0m"
}

# 检查进程是否运行
is_running() {
    local pid_file=$1
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p "$pid" > /dev/null 2>&1; then
            return 0
        else
            rm -f "$pid_file"
        fi
    fi
    return 1
}

# 停止进程
stop_process() {
    local pid_file=$1
    local process_name=$2

    if ! is_running "$pid_file"; then
        print_info "[INFO] ${process_name} 未运行(跳过)..."
        return 1
    fi

    local pid=$(cat "$pid_file")
    print_info "[INFO] 停止 ${process_name}(PID: $pid)..."

    kill -TERM "$pid" 2>/dev/null

    # 在10秒内持续检查进程是否结束
    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    # 如果10秒进程仍未停止, 强制终止
    if ps -p "$pid" > /dev/null 2>&1; then
        print_warn "[WARN] ${process_name} 未正常退出, 强制终止..."
        kill -9 "$pid" 2>/dev/null
    fi

    rm -f "$pid_file"
    print_info "[INFO] ${process_name} 已停止..."
    return 0
}

# 启动 Celery Worker 服务
start_celery_worker() {
    if is_running "$CELERY_WORKER_PID"; then
        local pid=$(cat "$CELERY_WORKER_PID")
        print_warn "[WARN] Celery Worker 已在运行(PID: $pid)"
        return 1
    fi

    print_info "[INFO] 启动 Celery Worker (并发数: ${CELERY_WORKER_CONCURRENCY}, 队列: ${CELERY_WORKER_QUEUES})..."

    celery -A "$CELERY_APP" worker \
        --loglevel=info \
        --concurrency=${CELERY_WORKER_CONCURRENCY} \
        --queues=${CELERY_WORKER_QUEUES} \
        --logfile="$CELERY_WORKER_LOG" \
        --pidfile="$CELERY_WORKER_PID" \
        --pool=solo \
        --detach

    sleep 3

    if is_running "$CELERY_WORKER_PID"; then
        local pid=$(cat "$CELERY_WORKER_PID")
        print_info "[INFO] Celery Worker 启动成功(PID: $pid)"
        print_info "[INFO] 日志文件: $CELERY_WORKER_LOG"
        return 0
    else
        print_error "[ERROR] Celery Worker 启动失败, 请查看日志: $CELERY_WORKER_LOG"
        return 1
    fi
}

# 启动 Celery Beat 服务
start_celery_beat() {
    if is_running "$CELERY_BEAT_PID"; then
        local pid=$(cat "$CELERY_BEAT_PID")
        print_warn "[WARN] Celery Beat 已在运行(PID: $pid)"
        return 1
    fi

    print_info "[INFO] 启动 Celery Beat (调度器: ${CELERY_BEAT_SCHEDULER})..."

    celery -A "$CELERY_APP" beat \
        --loglevel=info \
        --scheduler="$BEAT_SCHEDULER" \
        --logfile="$CELERY_BEAT_LOG" \
        --pidfile="$CELERY_BEAT_PID" \
        --detach

    sleep 3

    if is_running "$CELERY_BEAT_PID"; then
        local pid=$(cat "$CELERY_BEAT_PID")
        print_info "[INFO] Celery Beat 启动成功(PID: $pid)"
        print_info "[INFO] 日志文件: $CELERY_BEAT_LOG"
        return 0
    else
        print_error "[ERROR] Celery Beat 启动失败, 请查看日志: $CELERY_BEAT_LOG"
        return 1
    fi
}

# 停止 Celery Worker 服务
stop_celery_worker() {
    stop_process "$CELERY_WORKER_PID" "Celery Worker"
}

# 停止 Celery Beat 服务
stop_celery_beat() {
    stop_process "$CELERY_BEAT_PID" "Celery Beat"
}

# 查看 Celery 服务状态
celery_status() {
    echo "========== Celery 进程状态 =========="

    if is_running "$CELERY_WORKER_PID"; then
        local pid=$(cat "$CELERY_WORKER_PID")
        echo "[✓] Celery Worker: 运行中(PID: $pid)"
    else
        echo "[×] Celery Worker: 未运行"
    fi

    if is_running "$CELERY_BEAT_PID"; then
        local pid=$(cat "$CELERY_BEAT_PID")
        echo "[✓] Celery Beat: 运行中(PID: $pid)"
    else
        echo "[×] Celery Beat: 未运行"
    fi

    echo ""
    echo "日志文件:"
    echo "  Worker: $CELERY_WORKER_LOG"
    echo "  Beat:   $CELERY_BEAT_LOG"
    echo "========== Celery 进程状态 =========="
}


main() {
    case "${1:-}" in
        start)
            # 启动 Celery Worker 和 Celery Beat 服务(用法: ./celery_start.sh start [并发数])
            start_celery_worker
            start_celery_beat
            ;;
        stop)
            # 停止 Celery Worker 和 Celery Beat 服务
            stop_celery_worker
            stop_celery_beat
            ;;
        restart)
            # 重启 Celery Worker 和 Celery Beat 服务(用法: ./celery_start.sh restart [并发数])
            stop_celery_worker
            stop_celery_beat
            sleep 2
            if [ -n "$2" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            start_celery_worker
            start_celery_beat
            ;;
        status)
            # 查看 Celery 服务状态
            celery_status
            ;;
        start-worker)
            # 仅启动 Celery Worker 服务(用法: ./celery_start.sh start-worker [并发数])
            if [ -n "$2" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            start_celery_worker
            ;;
        stop-worker)
            # 仅停止 Celery Worker 服务
            stop_celery_worker
            ;;
        start-beat)
            # 仅启动 Celery Beat 服务
            start_celery_beat
            ;;
        stop-beat)
            # 仅停止 Celery Beat 服务
            stop_celery_beat
            ;;
        *)
            echo "==================== Celery 启动脚本说明 ===================="
            echo ""
            echo "命令说明:"
            echo "  start [并发数]         # 启动Celery Worker和Celery Beat服务(默认4并发数)"
            echo "  stop                  # 停止Celery Worker和Celery Beat服务"
            echo "  restart [并发数]       # 重启Celery Worker和Celery Beat服务"
            echo "  status                # 查看Celery服务状态"
            echo "  start-worker [并发数]  # 仅启动Celery Worker服务"
            echo "  stop-worker           # 仅停止Celery Worker服务"
            echo "  start-beat            # 仅启动Celery Beat服务"
            echo "  stop-beat             # 仅停止Celery Beat服务"
            echo ""
            echo "命令用法:"
            echo "  $0 start              # 启动Celery Worker(并发4)和Celery Beat服务"
            echo "  $0 start 8            # 启动Celery Worker(并发8)和Celery Beat服务"
            echo "  $0 restart 8          # 重启Celery Worker(并发8)和Celery Beat服务"
            echo "  $0 status             # 查看Celery服务状态"
            echo "  $0 stop               # 停止所有Celery服务"
            echo ""
            echo "使用提示:"
            echo "  1. 首次使用前, 请确保已安装依赖"
            echo "  2. 确保Redis服务已经启动且与配置一致"
            echo "  3. 日志文件位置: $CELERY_LOG_DIR"
            echo "  4. Celery Worker并发数建议设置为CPU核心数(需注意服务器性能吃紧)"
            echo "==================== Celery 启动脚本说明 ===================="
            exit 1
            ;;
    esac
}

main "$@"
