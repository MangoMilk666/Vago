#!/usr/bin/env bash
# ─── Vago 本地联调一键启动脚本 ────────────────────────────────────────────────
# 架构：Java 单体(8080) + Python AI(8000) + Vite 前端(5173)
# 用法：./dev-up.sh [--no-backend] [--no-ai] [--no-web]
#   按 Ctrl+C 停止所有服务

# 如果被 sh 调用（而非 bash），自动用 bash 重新执行
[ -z "${BASH_VERSION:-}" ] && exec bash "$0" "$@"

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVICES_DIR="$ROOT_DIR/services"
WEB_DIR="$ROOT_DIR/apps/vago-web"
AI_DIR="$SERVICES_DIR/vago-ai"
BACKEND_DIR="$SERVICES_DIR/vago-backend"

# ── 启动开关 ─────────────────────────────────────────────────────────────────
START_BACKEND=1
START_AI=1
START_WEB=1

usage() {
  cat <<'EOF'
用法：
  ./dev-up.sh [选项]

选项：
  --no-backend    跳过 Java 单体后端（vago-backend，:8080）
  --no-ai         跳过 Python AI 服务（vago-ai，:8000）
  --no-web        跳过 Web 前端（vago-web，:5173）
  -h, --help      显示帮助

示例：
  # 一键全栈启动
  ./dev-up.sh

  # 只启动后端（不启前端和 AI）
  ./dev-up.sh --no-ai --no-web

  # 只启动前端（后端已运行）
  ./dev-up.sh --no-backend --no-ai
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-backend) START_BACKEND=0; shift ;;
    --no-ai)      START_AI=0;      shift ;;
    --no-web)     START_WEB=0;     shift ;;
    -h|--help)    usage; exit 0 ;;
    *) printf "未知参数：%s\n" "$1" >&2; usage; exit 1 ;;
  esac
done

# ─── 工具函数 ─────────────────────────────────────────────────────────────────
info()    { printf "\033[36m[INFO]\033[0m  %s\n" "$*" >&2; }
success() { printf "\033[32m[OK]\033[0m    %s\n" "$*" >&2; }
warn()    { printf "\033[33m[WARN]\033[0m  %s\n" "$*" >&2; }
error()   { printf "\033[31m[ERROR]\033[0m %s\n" "$*" >&2; }

# ─── 检查依赖命令 ─────────────────────────────────────────────────────────────
check_command() {
  local cmd="$1"
  if ! command -v "$cmd" &>/dev/null; then
    error "未找到命令：$cmd，请先安装"
    exit 1
  fi
}

# ─── 检查端口是否已被占用 ─────────────────────────────────────────────────────
check_port_free() {
  local port="$1"
  local name="$2"
  if lsof -iTCP:"$port" -sTCP:LISTEN -n -P &>/dev/null; then
    warn "端口 $port ($name) 已被占用，跳过启动"
    return 1
  fi
  return 0
}

# ─── 等待端口就绪（轮询，最长 90s）──────────────────────────────────────────
wait_for_port() {
  local port="$1"
  local name="$2"
  local max=90
  local count=0
  info "等待 $name 就绪 (端口 $port)..."
  while ! nc -z localhost "$port" &>/dev/null; do
    sleep 1
    count=$((count + 1))
    if [[ $count -ge $max ]]; then
      error "$name 在 ${max}s 内未就绪，请查看日志：$ROOT_DIR/.log/"
      return 1
    fi
  done
  success "$name 已就绪"
}

# ─── 检查基础设施（MySQL / Redis）─────────────────────────────────────────────
check_infra() {
  info "检查 MySQL (3306)..."
  if ! nc -z localhost 3306 &>/dev/null; then
    error "MySQL 未启动，请先执行：brew services start mysql"
    exit 1
  fi
  success "MySQL 就绪"

  info "检查 Redis (6379)..."
  if ! nc -z localhost 6379 &>/dev/null; then
    warn "Redis 未启动，部分功能不可用 → brew services start redis"
  else
    success "Redis 就绪"
  fi
}

# ─── Maven 构建（跳过测试）───────────────────────────────────────────────────
build_java_module() {
  local module_dir="$1"
  local module_name="$2"
  info "构建 $module_name..."
  (cd "$module_dir" && mvn package -DskipTests -q)
  success "$module_name 构建完成"
}

# ─── 查找产出 JAR（排除 original- 前缀）──────────────────────────────────────
find_jar() {
  local module_dir="$1"
  local jar
  jar="$(find "$module_dir/target" -maxdepth 1 -name "*.jar" ! -name "original-*.jar" 2>/dev/null | head -1)"
  if [[ -z "$jar" ]]; then
    error "未找到 JAR：$module_dir/target/*.jar，请先构建"
    exit 1
  fi
  printf '%s' "$jar"
}

# ─── Python venv 管理 ────────────────────────────────────────────────────────
ensure_ai_venv() {
  local venv_dir="$AI_DIR/.venv"
  if [[ ! -x "$venv_dir/bin/python" ]]; then
    info "初始化 Python 虚拟环境..."
    python3 -m venv "$venv_dir"
  fi
  info "安装/更新 Python 依赖..."
  "$venv_dir/bin/pip" install -q -r "$AI_DIR/requirements.txt"
  success "Python 环境就绪"
}

# ─── 前端依赖 ────────────────────────────────────────────────────────────────
ensure_web_deps() {
  if [[ ! -d "$WEB_DIR/node_modules" ]]; then
    info "安装前端依赖（npm install）..."
    (cd "$WEB_DIR" && npm install)
    success "前端依赖安装完成"
  fi
}

# ─── PID 追踪 ────────────────────────────────────────────────────────────────
BACKEND_PID=""
AI_PID=""
WEB_PID=""

cleanup() {
  printf "\n" >&2
  info "正在停止所有服务..."
  [[ -n "$WEB_PID"     ]] && kill "$WEB_PID"     2>/dev/null || true
  [[ -n "$AI_PID"      ]] && kill "$AI_PID"      2>/dev/null || true
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  info "已停止"
}
trap cleanup EXIT INT TERM

# ════════════════════════════════════════════════════════════════════════════════
# 启动流程
# ════════════════════════════════════════════════════════════════════════════════
mkdir -p "$ROOT_DIR/.log"

printf "\n" >&2
printf "╔══════════════════════════════════════════╗\n" >&2
printf "║    🗺️  叠迹 Vago · 本地联调启动         ║\n" >&2
printf "╚══════════════════════════════════════════╝\n" >&2
printf "\n" >&2

check_command mvn
check_command java
check_command python3
check_command node
check_command npm
check_command nc

check_infra

# ── Java 单体后端 :8080 ───────────────────────────────────────────────────────
if [[ "$START_BACKEND" -eq 1 ]]; then
  if check_port_free 8080 "vago-backend"; then
    build_java_module "$BACKEND_DIR" "vago-backend"
    info "启动 vago-backend (端口 8080)..."
    java -jar "$(find_jar "$BACKEND_DIR")" \
         --spring.profiles.active=dev \
         > "$ROOT_DIR/.log/backend.log" 2>&1 &
    BACKEND_PID=$!
    wait_for_port 8080 "vago-backend"
  fi
fi

# ── Python AI 服务 :8000 ──────────────────────────────────────────────────────
if [[ "$START_AI" -eq 1 ]]; then
  if check_port_free 8000 "vago-ai"; then
    ensure_ai_venv
    info "启动 vago-ai (端口 8000)..."
    (
      cd "$AI_DIR"
      .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload
    ) > "$ROOT_DIR/.log/ai.log" 2>&1 &
    AI_PID=$!
    wait_for_port 8000 "vago-ai"
  fi
fi

# ── Vite 前端 :5173 ───────────────────────────────────────────────────────────
if [[ "$START_WEB" -eq 1 ]]; then
  ensure_web_deps
  info "启动 vago-web (端口 5173)..."
  (cd "$WEB_DIR" && npm run dev) > "$ROOT_DIR/.log/web.log" 2>&1 &
  WEB_PID=$!
  wait_for_port 5173 "vago-web"
fi

# ─── 就绪摘要 ─────────────────────────────────────────────────────────────────
printf "\n" >&2
printf "════════════════════════════════════════════\n" >&2
success "所有服务已就绪！"
[[ "$START_BACKEND" -eq 1 ]] && printf "  Java 后端  →  http://localhost:8080/swagger-ui.html\n" >&2
[[ "$START_AI"      -eq 1 ]] && printf "  AI  服务   →  http://localhost:8000/docs\n" >&2
[[ "$START_WEB"     -eq 1 ]] && printf "  Web 前端   →  http://localhost:5173\n" >&2
printf "\n  日志目录   →  $ROOT_DIR/.log/\n" >&2
printf "════════════════════════════════════════════\n\n" >&2
printf "按 Ctrl+C 停止所有服务\n" >&2

wait
