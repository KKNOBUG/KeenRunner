#!/bin/bash
# Celery Worker / Beat 部署脚本
# 原手动部署流程:
#   cd /zdhgj/python_projects/fastapi-toolbox-runner
#   source .venv/bin/activate
#   pkill -f -9 “backend_main:app”
#   pkill -f -9 celery
#   nohup celery -A celery_scheduler.celery_worker worker -Q 8520_default,8520_autotest -c 4 -l INFO > /zdhgj/python_projects/fastapi-toolbox-runner/output/logs/celery_logs/celery_worker.log 2>&1 &
#   nohup celery -A celery_scheduler.celery_worker beat -l INFO > /zdhgj/python_projects/fastapi-toolbox-runner/output/logs/celery_logs/celery_beat.log 2>&1 &
#   ps aux | grep celery
#   nohup gunicorn -c gunicorn.conf.py backend_main:app > /zdhgj/python_projects/fastapi-toolbox-runner/toolbox-runner.log 2>&1
#   ps aux | grep gunicorn
# 现自动部署流程
#   cd /zdhgj/python_projects/fastapi-toolbox-runner
#   ./celery_deploy.sh start|restart|stop|status ...
# 同机多实例: 各部署目录 .env 的 SERVER_PORT 错开；共用 Redis 时 CELERY_REDBEAT_DB 必须不同

# 脚本所在目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 顶层包导入，PYTHONPATH 指向项目根
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
CELERY_APP="celery_scheduler.celery_worker:celery"
CELERY_WORKER_CONCURRENCY="${CELERY_WORKER_CONCURRENCY:-4}"
CELERY_WORKER_QUEUES="${CELERY_WORKER_QUEUES:-${SERVER_PORT}_default,${SERVER_PORT}_autotest}"
CELERY_BEAT_SCHEDULER="${CELERY_BEAT_SCHEDULER:-redbeat.schedulers:RedBeatScheduler}"
CELERY_LOG_DIR="${PROJECT_ROOT}/output/logs/celery_logs"
mkdir -p "$CELERY_LOG_DIR"
CELERY_WORKER_LOG="${CELERY_LOG_DIR}/Worker-${SERVER_PORT}.log"
CELERY_BEAT_LOG="${CELERY_LOG_DIR}/Beat-${SERVER_PORT}.log"
CELERY_WORKER_PID="${PROJECT_ROOT}/celery_worker_${SERVER_PORT}.pid"
CELERY_BEAT_PID="${PROJECT_ROOT}/celery_beat_${SERVER_PORT}.pid"

handle_error() {
  print_error "错误信息：$1"
  exit 1
}

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

check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 未安装, 请先安装..."
        exit 1
    fi
}

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

# 校验 PID 对应进程确为目标服务，防 PID 复用误杀无关进程
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

    local pid=$(cat "$pid_file")

    if ! pid_is_service "$pid" "$service_keyword"; then
        print_warn "PID $pid 已被无关进程复用, 不执行终止, 仅清理过期PID文件"
        rm -f "$pid_file"
        return 1
    fi

    print_info "停止 ${process_name}(PID: $pid)..."

    kill -TERM "$pid" 2>/dev/null

    local count=0
    while ps -p "$pid" > /dev/null 2>&1 && [ $count -lt 10 ]; do
        sleep 1
        count=$((count + 1))
    done

    if ps -p "$pid" > /dev/null 2>&1; then
        print_warn "${process_name} 未正常退出, 强制终止..."
        kill -9 "$pid" 2>/dev/null
    fi

    rm -f "$pid_file"
    print_info "${process_name} 已停止..."
    return 0
}

# 步骤1: 停止旧服务
stop_services() {
    print_step "步骤1: 停止旧服务"
    stop_process "$CELERY_WORKER_PID" "Celery Worker" "celery"
    stop_process "$CELERY_BEAT_PID" "Celery Beat" "celery"
    sleep 2
}

# 步骤2: 启动Celery Worker
start_celery_worker() {
    print_step "步骤2: 启动Celery Worker"

    check_command "celery"

    if is_running "$CELERY_WORKER_PID"; then
        print_warn "Celery Worker已在运行, 跳过启动"
        return 0
    fi

    print_info "启动 Celery Worker (并发数: ${CELERY_WORKER_CONCURRENCY}, 队列: ${CELERY_WORKER_QUEUES})..."

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
        local pid=$(cat "$CELERY_WORKER_PID")
        print_info "Celery Worker 启动成功(PID: $pid)"
        print_info "PID文件: $CELERY_WORKER_PID"
        print_info "日志文件: $CELERY_WORKER_LOG"
        touch "$CELERY_WORKER_LOG" 2>/dev/null
    else
        handle_error "Celery Worker 启动失败, 请检查日志: tail -n 50 $CELERY_WORKER_LOG"
    fi
}

# 步骤3: 启动Celery Beat
start_celery_beat() {
    print_step "步骤3: 启动Celery Beat"

    check_command "celery"

    if is_running "$CELERY_BEAT_PID"; then
        print_warn "Celery Beat已在运行, 跳过启动"
        return 0
    fi

    print_info "启动 Celery Beat (调度器: ${CELERY_BEAT_SCHEDULER})..."

    export CELERY_LOGFILE="${CELERY_BEAT_LOG}"
    celery -A "$CELERY_APP" beat \
        --loglevel=INFO \
        --scheduler="${CELERY_BEAT_SCHEDULER}" \
        --logfile="${CELERY_BEAT_LOG}" \
        --pidfile="${CELERY_BEAT_PID}" \
        --detach

    sleep 3

    if is_running "$CELERY_BEAT_PID"; then
        local pid=$(cat "$CELERY_BEAT_PID")
        print_info "Celery Beat 启动成功(PID: $pid)"
        print_info "PID文件: $CELERY_BEAT_PID"
        print_info "日志文件: $CELERY_BEAT_LOG"
        touch "$CELERY_BEAT_LOG" 2>/dev/null
    else
        handle_error "Celery Beat 启动失败, 请检查日志: tail -n 50 $CELERY_BEAT_LOG"
    fi
}

# 步骤4: 检查服务状态
check_status() {
    print_step "步骤4: 检查服务状态"

    echo ""
    print_info "========== 服务运行状态 =========="

    if is_running "$CELERY_WORKER_PID"; then
        local pid=$(cat "$CELERY_WORKER_PID")
        print_info "[✓] Celery Worker: 运行中 (PID: $pid)"
    else
        print_error "[×] Celery Worker: 未运行"
    fi

    if is_running "$CELERY_BEAT_PID"; then
        local pid=$(cat "$CELERY_BEAT_PID")
        print_info "[✓] Celery Beat: 运行中 (PID: $pid)"
    else
        print_error "[×] Celery Beat: 未运行"
    fi

    print_info "日志文件: Worker=$CELERY_WORKER_LOG"
    print_info "日志文件: Beat=$CELERY_BEAT_LOG"

    echo ""
    print_info "========== 服务运行状态 =========="
}

full_deploy() {
    print_info "开始完整部署流程..."
    print_info "项目目录: $PROJECT_ROOT"
    print_info "Celery 应用: $CELERY_APP"
    print_info "Worker 队列: $CELERY_WORKER_QUEUES"
    echo ""

    stop_services
    start_celery_worker
    start_celery_beat
    check_status
}

restart_services() {
    print_step "重启服务"

    stop_services
    sleep 2
    start_celery_worker
    start_celery_beat
    check_status
}

stop_all() {
    print_step "停止所有服务"
    stop_services
}

show_status() {
    print_step "查看服务运行状态"
    check_status
}

main() {
    case "${1:-}" in
        start)
            if [ -n "${2:-}" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            full_deploy
            ;;
        restart)
            if [ -n "${2:-}" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            restart_services
            ;;
        stop)
            stop_all
            ;;
        status)
            show_status
            ;;
        start-worker)
            if [ -n "${2:-}" ]; then
                CELERY_WORKER_CONCURRENCY=$2
            fi
            start_celery_worker
            ;;
        stop-worker)
            stop_process "$CELERY_WORKER_PID" "Celery Worker" "celery"
            ;;
        start-beat)
            start_celery_beat
            ;;
        stop-beat)
            stop_process "$CELERY_BEAT_PID" "Celery Beat" "celery"
            ;;
        *)
            echo "==================== Celery 部署脚本 ===================="
            echo "命令说明:"
            echo "  start [并发数]         # 完整部署(停止服务 -> 启动 Worker -> 启动 Beat)"
            echo "  restart [并发数]       # 重启 Worker 与 Beat"
            echo "  stop                  # 停止 Worker 与 Beat"
            echo "  status                # 查看服务运行状态"
            echo "  start-worker [并发数]  # 仅启动 Worker"
            echo "  stop-worker           # 仅停止 Worker"
            echo "  start-beat            # 仅启动 Beat"
            echo "  stop-beat             # 仅停止 Beat"
            echo ""
            echo "使用提示:"
            echo "  1. 首次使用前, 请确保已安装依赖并激活虚拟环境"
            echo "  2. 确保 .env 配置正确(SERVER_PORT/数据库/Redis库号)"
            echo "  3. 同机多实例: 各目录 SERVER_PORT 错开; 共用 Redis 时 CELERY_REDBEAT_DB 必须不同"
            echo "  4. 自定义 logging 时必须由 setup_loggers 接收 --logfile 并挂文件 sink"
            echo "  5. FastAPI 服务由 fastapi_deploy.sh 单独管理"
            echo "==================== Celery 部署脚本 ===================="
            exit 1
            ;;
    esac
}

main "$@"