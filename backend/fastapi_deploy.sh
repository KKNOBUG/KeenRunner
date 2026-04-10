#!/bin/bash

# 配置脚本所在目录
PROJECT_ROOT="服务器上的后端项目所在目录"

# 配置Gunicorn服务
GUNICORN_APP="backend_main:app"
GUNICORN_CONFIG_FILE="${PROJECT_ROOT}/gunicorn.configuration.py"
GUNICORN_PID_FILE="${PROJECT_ROOT}/gunicorn.pid"

# 配置Celery应用路径
CELERY_APP="celery_scheduler.celery_worker:celery"
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_QUEUES="autotest_queue,default"
CELERY_BEAT_SCHEDULER="redbeat.schedulers:RedBeatScheduler"

# Celery日志和PID文件
CELERY_LOG_DIR="${PROJECT_ROOT}/output/logs/celery_logs"
mkdir -p "$CELERY_LOG_DIR"
CELERY_WORKER_LOG="${CELERY_LOG_DIR}/celery_worker.log"
CELERY_BEAT_LOG="${CELERY_LOG_DIR}/celery_beat.log"
CELERY_WORKER_PID="${PROJECT_ROOT}/celery_worker.pid"
CELERY_BEAT_PID="${PROJECT_ROOT}/celery_beat.pid"

# 配置Git服务
GIT_BRANCH="发布分支"
GIT_USERNAME="GIT账号"
GIT_PASSWORD="GIT密码"

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

# 检查命令是否存在
check_command() {
    if ! command -v "$1" &> /dev/null; then
        print_error "$1 未安装, 请先安装..."
        exit 1
    fi
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


# 停止Celery Worker
stop_celery_worker() {
    stop_process "$CELERY_WORKER_PID" "Celery Worker"
}

# 停止Celery Beat
stop_celery_beat() {
    stop_process "$CELERY_BEAT_PID" "Celery Beat"
}

# 步骤1: 停止旧服务
stop_services() {
    print_step "步骤1: 停止旧服务"

    # 停止Celery
    print_info "停止Celery Beat服务..."
    stop_celery_beat
    print_info "停止Celery Worker服务..."
    stop_celery_worker

    # 停止Gunicorn
    print_info "停止Gunicorn服务..."
    stop_process "$GUNICORN_PID_FILE" "Gunicorn"

    # 等待一下确保进程完全停止
    sleep 2
}

# 步骤2: 拉取最新代码(仅master分支)
pull_code() {
    print_step "步骤2: 拉取master分支最新代码"

    check_command "git"

    print_info "拉取 ${GIT_REMOTE}/${GIT_BRANCH} 最新代码..."

#    # 检查是否有未提交的更改
#    if ! git diff-index --quiet HEAD --; then
#        print_warn "检测到存在更改但未提交的文件(放弃), 将回滚本地更改..."
#        git reset --hard HEAD || {
#          print_error "回滚本地代码更改失败..."
#          exit 1
#        }
#        print_info "已成功回滚本地代码更改..."
#    fi

    # 拉取代码(仅master分支)
    expect <<EOF
spawn git pull origin "$GIT_BRANCH"
expect "Username"
send "${GIT_USERNAME}\r"
expect "Password"
send "${GIT_PASSWORD}\r"
expect eof
EOF
    if [ $? -ne 0 ]; then
      handle_error "拉取${GIT_BRANCH}分支代码失败"
    fi
    print_info "代码更新成功(master分支)"
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

# 步骤3: 启动Celery
start_celery() {
    print_step "步骤3: 启动Celery服务"

    check_command "celery"

    start_celery_worker || {
        print_error "启动 Celery Worker 服务失败..."
        exit 1
    }

    start_celery_beat || {
        print_error "启动 Celery Beat 服务失败..."
        exit 1
    }

    # 等待一下确保Celery启动成功
    sleep 1
}

# 步骤4: 启动FastAPI应用
start_fastapi() {
    print_step "步骤4: 启动FastAPI应用"

    check_command "gunicorn"

    if is_running "$GUNICORN_PID_FILE"; then
        print_warn "Gunicorn已在运行, 跳过启动"
        return 0
    fi

    # 检查配置文件是否存在
    if ! [ -f "$GUNICORN_CONFIG_FILE" ]; then
      print_error "Gunicorn配置文件不存在: $GUNICORN_CONFIG_FILE"
      exit 1
    fi

    print_info "启动Gunicorn服务(使用配置文件: $GUNICORN_CONFIG_FILE)"

    nohup gunicorn "$GUNICORN_APP" \
        --config="$GUNICORN_CONFIG_FILE" \
        --pid="$GUNICORN_PID_FILE" \
        > /dev/null 2>&1

    sleep 5

    if is_running "$GUNICORN_PID_FILE"; then
        local pid=$(cat "$GUNICORN_PID_FILE")
        print_info "Gunicorn服务启动成功 (PID: $pid)"
        print_info "PID文件: $GUNICORN_PID_FILE"
    else
        print_error "Gunicorn服务启动失败, 请检查配置文件: $GUNICORN_CONFIG_FILE"
        exit 1
    fi
}

# 步骤5: 检查服务状态
check_status() {
    print_step "步骤5: 检查服务状态"

    echo ""
    print_info "========== 服务运行状态 =========="

    # 检查Gunicorn服务
    if is_running "$GUNICORN_PID_FILE"; then
        local pid=$(cat "$GUNICORN_PID_FILE")
        print_info "[✓] Gunicorn: 运行中 (PID: $pid)"
    else
        print_error "[×] Gunicorn: 未运行"
    fi

    # 检查Celery Worker服务
    if is_running "$CELERY_WORKER_PID"; then
        local pid=$(cat "$CELERY_WORKER_PID")
        print_info "[✓] Celery Worker: 运行中 (PID: $pid)"
    else
        print_error "[×] Celery Worker: 未运行"
    fi

    # 检查Celery Beat服务
    if is_running "$CELERY_BEAT_PID"; then
        local pid=$(cat "$CELERY_BEAT_PID")
        print_info "[✓] Celery Beat: 运行中 (PID: $pid)"
    else
        print_error "[×] Celery Beat: 未运行"
    fi

    echo ""
    print_info "部署完成！"
    print_info "========== 服务运行状态 =========="
}

# 完整部署流程
full_deploy() {
    print_info "开始完整部署流程..."
    print_info "项目目录: $SCRIPT_DIR"
    print_info "Git拉取分支: $GIT_BRANCH"
    print_info "Gunicorn 配置: $GUNICORN_CONFIG_FILE"
    print_info "Celery Worker并发数: $CELERY_WORKER_CONCURRENCY"
    echo ""

    stop_services
    pull_code
    start_celery
    start_fastapi
    check_status
}

# 仅重启服务(不拉取代码)
restart_services() {
    print_step "重启服务(不拉取代码)"

    stop_services
    sleep 2
    start_celery
    start_fastapi
    check_status
}

# 仅停止服务
stop_all() {
    print_step "停止所有服务"
    stop_services
}

# 查看状态
show_status() {
    print_step "查看服务运行状态"
    check_status
}

# 主逻辑
main() {
    case "${1:-}" in
        start)
            # 完整部署
            full_deploy
            ;;
        restart)
            # 仅重启服务
            restart_services
            ;;
        stop)
            # 停止服务
            stop_all
            ;;
        status)
            # 查看状态
            show_status
            ;;
        *)
            echo "==================== ToolBox 项目部署脚本 ===================="
            echo "命令说明:"
            echo "  start         # 完整部署(停止服务 -> 拉取master分支代码 -> 启动Celery服务 -> 启动FastAPI服务)"
            echo "  restart       # 仅重启服务(不拉取代码)"
            echo "  stop          # 停止所有服务"
            echo "  status        # 查看服务运行状态"
            echo ""
            echo "使用提示:"
            echo "  1. 首次使用前, 请确保已安装依赖"
            echo "  2. 确保gunicorn.configuration.py配置文件正确"
            echo "  3. 确保configure.project_config.py配置文件正确"
            echo "  4. 发生改动但未提交的文件会被直接放弃, 由 $GIT_BRANCH 分支代码覆盖"
            echo "==================== ToolBox 项目部署脚本 ===================="
            exit 1
            ;;
    esac
}

main "$@"
