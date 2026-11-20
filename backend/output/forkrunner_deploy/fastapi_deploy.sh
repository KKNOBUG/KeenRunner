#!/bin/bash
# FastAPI 部署脚本
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
#   ./fastapi_deploy.sh start|restart|stop|status
# 同机多实例: 各部署目录 .env 的 SERVER_PORT 错开

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

# 配置Gunicorn服务
GUNICORN_APP="backend_main:app"
GUNICORN_CONFIG_FILE="${PROJECT_ROOT}/gunicorn.conf.py"
GUNICORN_PID_FILE="${PROJECT_ROOT}/gunicorn_${SERVER_PORT}.pid"
FASTAPI_LOG_FILE="${PROJECT_ROOT}/backend_main_${SERVER_PORT}.log"

# 配置Git服务: 与手动执行git pull origin toolbox-runner/git reset --hard origin/toolbox-runner命令保持一致
GIT_BRANCH="toolbox-runner"
GIT_USERNAME="CS4224"
GIT_PASSWORD='KFuser01@!'

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
    stop_process "$GUNICORN_PID_FILE" "Gunicorn" "gunicorn"
    sleep 2
}

# 步骤2: 强制拉取远端 GIT_BRANCH 覆盖本地（fetch + reset，不做合并）
pull_code() {
    print_step "步骤2: 拉取 ${GIT_BRANCH} 分支最新代码"

    check_command "git"
    check_command "expect"

    print_info "拉取 ${GIT_BRANCH} 分支最新代码..."

    # 交互认证拉取远端分支
    expect <<EOF
set timeout 60
spawn git fetch origin "$GIT_BRANCH"
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
expect eof
EOF
    pull_rc=$?

    if [ "$pull_rc" -ne 0 ]; then
        handle_error "git fetch 失败, 请检查网络/凭证/远端分支后重试"
    fi

    # 放弃本地改动, 由远端 GIT_BRANCH 最新代码覆盖
    if ! git reset --hard FETCH_HEAD; then
        handle_error "git reset --hard FETCH_HEAD 失败"
    fi
    print_info "代码更新成功(${GIT_BRANCH} 分支)"
}

# 步骤3: 启动FastAPI应用
start_fastapi() {
    print_step "步骤3: 启动FastAPI应用"

    check_command "gunicorn"

    if is_running "$GUNICORN_PID_FILE"; then
        print_warn "Gunicorn已在运行, 跳过启动"
        return 0
    fi

    if ! [ -f "$GUNICORN_CONFIG_FILE" ]; then
      print_error "Gunicorn配置文件不存在: $GUNICORN_CONFIG_FILE"
      exit 1
    fi

    print_info "启动Gunicorn服务(使用配置文件: $GUNICORN_CONFIG_FILE)"

    nohup gunicorn -c "$GUNICORN_CONFIG_FILE" "$GUNICORN_APP" \
        --pid="$GUNICORN_PID_FILE" \
        --name="gunicorn_${SERVER_PORT}" \
        > "$FASTAPI_LOG_FILE" 2>&1 &

    sleep 10

    if is_running "$GUNICORN_PID_FILE"; then
        local pid=$(cat "$GUNICORN_PID_FILE")
        print_info "Gunicorn服务启动成功 (PID: $pid)"
        print_info "PID文件: $GUNICORN_PID_FILE"
        print_info "日志文件: $FASTAPI_LOG_FILE"
    else
        print_error "Gunicorn服务启动失败, 请检查日志: tail -n 50 $FASTAPI_LOG_FILE"
        exit 1
    fi
}

# 步骤4: 检查服务状态
check_status() {
    print_step "步骤4: 检查服务状态"

    echo ""
    print_info "========== 服务运行状态 =========="

    if is_running "$GUNICORN_PID_FILE"; then
        local pid=$(cat "$GUNICORN_PID_FILE")
        print_info "[✓] Gunicorn: 运行中 (PID: $pid)"
    else
        print_error "[×] Gunicorn: 未运行"
    fi

    echo ""
    print_info "========== 服务运行状态 =========="
}

full_deploy() {
    print_info "开始完整部署流程..."
    print_info "项目目录: $PROJECT_ROOT"
    print_info "Git拉取分支: $GIT_BRANCH"
    print_info "Gunicorn 配置: $GUNICORN_CONFIG_FILE"
    echo ""

    stop_services
    pull_code
    start_fastapi
    check_status
}

restart_services() {
    print_step "重启服务(不拉取代码)"

    stop_services
    sleep 2
    start_fastapi
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
            full_deploy
            ;;
        restart)
            restart_services
            ;;
        stop)
            stop_all
            ;;
        status)
            show_status
            ;;
        *)
            echo "==================== FastAPI 部署脚本 ===================="
            echo "命令说明:"
            echo "  start         # 完整部署(停止服务 -> 拉取 $GIT_BRANCH 分支代码 -> 启动 FastAPI 服务)"
            echo "  restart       # 仅重启服务(不拉取代码)"
            echo "  stop          # 停止 FastAPI 服务"
            echo "  status        # 查看服务运行状态"
            echo ""
            echo "使用提示:"
            echo "  1. 首次使用前, 请确保已安装依赖并激活虚拟环境"
            echo "  2. 确保 gunicorn.conf.py 配置文件正确(bind 随 .env 的 SERVER_PORT)"
            echo "  3. 确保 .env 配置正确(SERVER_PORT/数据库/Redis库号)"
            echo "  4. start 强制拉取 $GIT_BRANCH 覆盖本地(放弃未提交改动); 不想拉取用 restart"
            echo "  5. Celery 服务由 celery_deploy.sh 单独管理"
            echo "==================== FastAPI 部署脚本 ===================="
            exit 1
            ;;
    esac
}

main "$@"