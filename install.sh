#!/bin/bash
#
# article-craft 安装脚本
# 用法: bash install.sh
#

set -e

PLUGIN_ROOT="$(cd "$(dirname "$0")" && pwd)"
SCRIPTS_DIR="$PLUGIN_ROOT/scripts"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

info()    { echo -e "${CYAN}[INFO]${RESET} $*"; }
success() { echo -e "${GREEN}[OK]${RESET}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET} $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*" >&2; }

header() {
  echo ""
  echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
  echo -e "${BOLD}  article-craft 安装向导${RESET}"
  echo -e "${BOLD}═══════════════════════════════════════════════════════${RESET}"
  echo ""
}

separator() {
  echo ""
  echo -e "${BOLD}── $1 ──${RESET}"
}

# =============================================================================
# 检查系统依赖
# =============================================================================
check_system() {
  separator "检查系统依赖"

  local missing=0

  # Python
  if command -v python3 >/dev/null 2>&1; then
    local py_ver
    py_ver=$(python3 --version 2>&1 | awk '{print $2}')
    success "Python: $py_ver"
  else
    error "Python 3 未安装"
    echo "  访问 https://www.python.org/downloads/ 下载安装"
    missing=$((missing + 1))
  fi

  # Node.js
  if command -v node >/dev/null 2>&1; then
    local node_ver
    node_ver=$(node --version 2>&1)
    success "Node.js: $node_ver"
  else
    warn "Node.js 未安装（PicGo 将跳过）"
    echo "  访问 https://nodejs.org/ 安装，或运行: brew install node"
  fi

  # npm
  if command -v npm >/dev/null 2>&1; then
    local npm_ver
    npm_ver=$(npm --version 2>&1)
    success "npm: $npm_ver"
  else
    warn "npm 未安装"
  fi

  # Git
  if command -v git >/dev/null 2>&1; then
    success "Git: $(git --version | awk '{print $3}')"
  else
    warn "Git 未安装"
  fi

  return 0
}

# =============================================================================
# 安装 Python 依赖
# =============================================================================
install_python_deps() {
  separator "安装 Python 依赖"

  if [ ! -f "$SCRIPTS_DIR/requirements.txt" ]; then
    error "requirements.txt 未找到: $SCRIPTS_DIR"
    return 1
  fi

  info "安装 Python 包..."

  # 检测 pip 命令
  local pip_cmd=""
  if command -v pip3 >/dev/null 2>&1; then
    pip_cmd="pip3"
  elif command -v pip >/dev/null 2>&1; then
    pip_cmd="pip"
  else
    error "未找到 pip，请先安装 Python"
    return 1
  fi

  # 升级 pip（避免某些系统老 pip 导致安装失败）
  info "升级 pip..."
  $pip_cmd install --upgrade pip -q 2>/dev/null || true

  # 安装依赖
  if $pip_cmd install -q -r "$SCRIPTS_DIR/requirements.txt"; then
    success "Python 依赖安装完成"
  else
    error "Python 依赖安装失败"
    echo "  手动运行: $pip_cmd install -r $SCRIPTS_DIR/requirements.txt"
    return 1
  fi
}

# =============================================================================
# 安装 Playwright（截图工具依赖）
# =============================================================================
install_playwright() {
  separator "安装 Playwright"

  # 检查 playwright 是否可用
  if python3 -c "from playwright.sync_api import sync_playwright" 2>/dev/null; then
    success "Playwright Python SDK 已安装"
    check_chromium || true
    return 0
  fi

  info "安装 Playwright..."
  if pip3 install -q playwright 2>/dev/null; then
    success "Playwright 安装完成"
    install_chromium
  else
    error "Playwright 安装失败"
    echo "  手动运行: pip3 install playwright && playwright install chromium"
    return 1
  fi
}

install_chromium() {
  info "安装 Chromium 浏览器（用于截图）..."
  if playwright install chromium 2>&1 | tail -5; then
    success "Chromium 安装完成"
  else
    warn "Chromium 安装可能失败，请手动运行: playwright install chromium"
  fi
}

check_chromium() {
  info "检查 Chromium..."
  if playwright install --dry-run chromium 2>&1 | grep -q "will install"; then
    warn "Chromium 未安装，运行: playwright install chromium"
  else
    success "Chromium 就绪"
  fi
}

# =============================================================================
# 安装 PicGo
# =============================================================================
install_picgo() {
  separator "安装 PicGo"

  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    warn "Node.js/npm 未安装，跳过 PicGo"
    echo "  如需图片上传功能，请先安装 Node.js: https://nodejs.org/"
    return 0
  fi

  if command -v picgo >/dev/null 2>&1; then
    success "PicGo 已安装: $(picgo --version 2>&1)"
    echo ""
    echo -e "  ${YELLOW}提示:${RESET} 如需重新配置图床，运行: ${BOLD}picgo set uploader${RESET}"
    return 0
  fi

  info "安装 PicGo CLI..."
  if npm install -g picgo 2>&1 | tail -3; then
    success "PicGo 安装完成"
    echo ""
    echo -e "${BOLD}下一步：配置图床${RESET}"
    echo "  运行以下命令，选择并配置你的图床服务:"
    echo "    ${BOLD}picgo set uploader${RESET}"
    echo ""
    echo "  推荐图床选项:"
    echo "    github  — GitHub + jsDelivr CDN（免费，推荐）"
    echo "    aliyun-oss — 阿里云 OSS"
    echo "    cos      — 腾讯云 COS"
    echo "    qiniu    — 七牛云"
    echo ""
    echo "  GitHub 图床配置示例:"
    echo "    token:  ghp_xxxxxxxxxxxx（GitHub Personal Access Token）"
    echo "    repo:   your-username/article-images"
    echo "    branch: main"
    echo "    customUrl: https://cdn.jsdelivr.net/gh/your-username/article-images"
  else
    warn "PicGo 安装可能失败，请手动运行: npm install -g picgo"
  fi
}

# =============================================================================
# 安装 yt-dlp（可选）
# =============================================================================
install_ytdlp() {
  separator "安装 yt-dlp（可选）"

  if command -v yt-dlp >/dev/null 2>&1; then
    success "yt-dlp 已安装: $(yt-dlp --version 2>&1)"
    return 0
  fi

  echo -n "  是否安装 yt-dlp（用于 YouTube 视频转文章）？[y/N]: "
  read -r answer
  if [[ "$answer" =~ ^[Yy]$ ]]; then
    info "安装 yt-dlp..."
    if pip3 install -q yt-dlp 2>/dev/null; then
      success "yt-dlp 安装完成"
    else
      warn "yt-dlp 安装失败，请手动运行: pip3 install yt-dlp"
    fi
  else
    info "跳过 yt-dlp（需要时可运行: pip3 install yt-dlp）"
  fi
}

# =============================================================================
# 检查 NotebookLM CLI（可选）
# =============================================================================
install_notebooklm_cli() {
  separator "检查 NotebookLM CLI（可选）"

  local notebooklm_cmd=""
  if command -v notebooklm >/dev/null 2>&1; then
    notebooklm_cmd="notebooklm"
  elif command -v nlm >/dev/null 2>&1; then
    notebooklm_cmd="nlm"
  elif command -v notebooklm-mcp >/dev/null 2>&1; then
    notebooklm_cmd="notebooklm-mcp"
  fi
  if [ -n "$notebooklm_cmd" ]; then
    success "NotebookLM CLI 已安装: $notebooklm_cmd"
    return 0
  fi

  echo -n "  是否安装 NotebookLM CLI（用于长文调研/资料整理）？[y/N]: "
  read -r answer
  if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    info "跳过 NotebookLM CLI（需要时可运行: uv tool install notebooklm-cli）"
    return 0
  fi

  if command -v uv >/dev/null 2>&1; then
    info "使用 uv 安装 notebooklm-cli..."
    if uv tool install notebooklm-cli >/dev/null 2>&1; then
      success "NotebookLM CLI 安装完成"
    else
      warn "uv 安装失败，尝试 pip3..."
      if pip3 install -q notebooklm-cli 2>/dev/null; then
        success "NotebookLM CLI 安装完成"
      else
        warn "NotebookLM CLI 安装失败，请手动运行: uv tool install notebooklm-cli"
        return 0
      fi
    fi
  elif command -v pip3 >/dev/null 2>&1; then
    info "使用 pip3 安装 notebooklm-cli..."
    if pip3 install -q notebooklm-cli 2>/dev/null; then
      success "NotebookLM CLI 安装完成"
    else
      warn "NotebookLM CLI 安装失败，请手动运行: pip3 install notebooklm-cli"
      return 0
    fi
  else
    warn "未找到 uv/pip3，无法自动安装 NotebookLM CLI"
    echo "  手动安装: uv tool install notebooklm-cli"
    return 0
  fi

  if command -v notebooklm >/dev/null 2>&1; then
    success "已验证命令可用: notebooklm"
  elif command -v nlm >/dev/null 2>&1; then
    success "已验证命令可用: nlm"
  elif command -v notebooklm-mcp >/dev/null 2>&1; then
    success "已验证兼容命令可用: notebooklm-mcp"
  else
    warn "安装完成，但当前 shell 尚未识别 NotebookLM CLI 命令"
    echo "  请重启终端后运行: nlm --help"
  fi
}

# =============================================================================
# 配置 MINIMAX_API_KEY
# =============================================================================
config_minimax_key() {
  separator "配置 Minimax API Key"

  local env_file="${HOME}/.claude/env.json"
  mkdir -p "$(dirname "$env_file")"
  # 优先用项目内的 env.example.json（跟着代码一起更新，结构永远最新），
  # 其次回落到用户家目录历史版本。
  local env_example=""
  if [ -f "$PLUGIN_ROOT/env.example.json" ]; then
    env_example="$PLUGIN_ROOT/env.example.json"
  elif [ -f "${HOME}/.claude/env.example.json" ]; then
    env_example="${HOME}/.claude/env.example.json"
  fi

  # 检查是否已有有效 key
  local existing_key=""
  if [ -f "$env_file" ]; then
    existing_key=$(python3 -c "import json; d=json.load(open('$env_file')); print(d.get('minimax_api_key',''))" 2>/dev/null || echo "")
    if [ -n "$existing_key" ] && [[ ! "$existing_key" =~ ^your- ]]; then
      success "MINIMAX_API_KEY 已配置"
      return 0
    fi
  fi

  # 检查 env.example.json 是否带了真实 key（极少见，但不打破历史行为）
  if [ -n "$env_example" ] && [ -f "$env_example" ]; then
    local example_key=""
    example_key=$(python3 -c "import json; d=json.load(open('$env_example')); print(d.get('minimax_api_key',''))" 2>/dev/null || echo "")
    if [ -n "$example_key" ] && [[ ! "$example_key" =~ ^your- ]]; then
      info "从 $env_example 复制配置到 env.json..."
      mkdir -p "$(dirname "$env_file")"
      cp "$env_example" "$env_file"
      success "MINIMAX_API_KEY 已配置"
      return 0
    fi
  fi

  echo ""
  echo "  ${YELLOW}需要配置 Minimax API Key 用于图片生成主链路${RESET}"
  echo ""
  echo "  1. 从 Minimax 控制台获取 API Key"
  echo "  2. 输入你的 API Key"
  echo ""
  echo -n "  API Key (输入后回车): "
  read -r api_key

  if [ -z "$api_key" ]; then
    warn "跳过 API Key 配置"
    echo "  稍后可编辑 $env_file 手动添加:"
    echo '    {"minimax_api_key": "YOUR_KEY_HERE"}'
    return 0
  fi

  api_key=$(echo "$api_key" | tr -d '[:space:]')

  # 创建或更新 env.json
  if [ -f "$env_file" ]; then
    # 保留现有配置，只更新 key
    python3 << PYEOF
import json, sys

with open('$env_file', 'r') as f:
    d = json.load(f)

d['minimax_api_key'] = '$api_key'

with open('$env_file', 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
PYEOF
  else
    # 创建新文件
    cat > "$env_file" << EOF
{
  "minimax_api_key": "$api_key",
  "image_model": "minimax-image-01",
  "minimax_image_model": "minimax-image-01",
  "gemini_image_model": "gemini-3-pro-image-preview"
}
EOF
  fi

  success "MINIMAX_API_KEY 已保存到 $env_file"
}

# =============================================================================
# 配置 GEMINI_API_KEY（可选）
# =============================================================================
config_gemini_key() {
  separator "配置 Gemini API Key（可选，用于 fallback / --enhance）"

  local env_file="${HOME}/.claude/env.json"
  local existing_key=""
  if [ -f "$env_file" ]; then
    existing_key=$(python3 -c "import json; d=json.load(open('$env_file')); print(d.get('gemini_api_key',''))" 2>/dev/null || echo "")
    if [ -n "$existing_key" ] && [[ ! "$existing_key" =~ ^your- ]]; then
      success "GEMINI_API_KEY 已配置"
      return 0
    fi
  fi

  echo -n "  是否配置 Gemini fallback Key（用于 fallback / --enhance）？[y/N]: "
  read -r answer
  if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    info "跳过 Gemini API Key（主链路仍可使用 Minimax）"
    return 0
  fi

  echo ""
  echo "  1. 访问 https://aistudio.google.com/app/apikey 获取 Gemini API Key"
  echo "  2. 输入你的 API Key"
  echo ""
  echo -n "  Gemini API Key (输入后回车): "
  read -r api_key

  if [ -z "$api_key" ]; then
    warn "未输入 Gemini API Key，跳过"
    return 0
  fi

  api_key=$(echo "$api_key" | tr -d '[:space:]')
  mkdir -p "$(dirname "$env_file")"
  if [ -f "$env_file" ]; then
    python3 << PYEOF
import json

with open('$env_file', 'r') as f:
    d = json.load(f)

d['gemini_api_key'] = '$api_key'

with open('$env_file', 'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
PYEOF
  else
    cat > "$env_file" << EOF
{
  "gemini_api_key": "$api_key"
}
EOF
  fi

  success "GEMINI_API_KEY 已保存到 $env_file"
}

# =============================================================================
# 验证安装
# =============================================================================
verify() {
  separator "验证安装"

  local ok=0

  echo ""
  echo "  检查项目          状态"
  echo "  ─────────────────────────────"

  # Python 包
  for pkg in google.genai PIL dotenv playwright requests; do
    if python3 -c "import ${pkg//-/_}" 2>/dev/null; then
      echo "  ${pkg}           OK"
    else
      echo "  ${pkg}           MISSING"
      ok=$((ok + 1))
    fi
  done

  # Playwright chromium
  if python3 -c "from playwright.sync_api import sync_playwright; sync_playwright().start().stop()" 2>/dev/null; then
    echo "  playwright        OK"
  else
    echo "  playwright        MISSING (run: playwright install chromium)"
    ok=$((ok + 1))
  fi

  # env.json
  if [ -f "${HOME}/.claude/env.json" ]; then
    echo "  env.json          OK"
  else
    echo "  env.json          MISSING"
    ok=$((ok + 1))
  fi

  # API keys
  local minimax_key=""
  local gemini_key=""
  if [ -f "${HOME}/.claude/env.json" ]; then
    minimax_key=$(python3 -c "import json; d=json.load(open('${HOME}/.claude/env.json')); print(d.get('minimax_api_key',''))" 2>/dev/null || echo "")
    gemini_key=$(python3 -c "import json; d=json.load(open('${HOME}/.claude/env.json')); print(d.get('gemini_api_key',''))" 2>/dev/null || echo "")
  fi
  if [ -n "$minimax_key" ] && [[ ! "$minimax_key" =~ ^your- ]]; then
    echo "  minimax_api_key   OK"
  else
    echo "  minimax_api_key   MISSING"
    ok=$((ok + 1))
  fi
  if [ -n "$gemini_key" ] && [[ ! "$gemini_key" =~ ^your- ]]; then
    echo "  gemini_api_key    OK (optional)"
  else
    echo "  gemini_api_key    SKIPPED (optional)"
  fi

  echo ""
  if [ $ok -eq 0 ]; then
    success "所有检查通过！"
  else
    warn "$ok 个项目未就绪，请向上滚动查看详情"
  fi

  return $ok
}

# =============================================================================
# 使用说明
# =============================================================================
usage() {
  separator "下一步"

  echo ""
  echo "  article-craft 安装完成！"
  echo ""
  echo "  ${BOLD}快速开始${RESET}:"
  echo ""
  echo "    /article-craft 写一篇关于 Go 并发编程的技术文章"
  echo ""
  echo "  ${BOLD}单独使用某个 skill${RESET}:"
  echo ""
  echo "    /article-craft:write        生成文章"
  echo "    /article-craft:images       生成图片"
  echo "    /article-craft:review       审核评分"
  echo "    /article-craft:lint        风格检查"
  echo "    /article-craft:screenshot   网页截图 + 分享卡片"
  echo "    /article-craft:youtube      YouTube 转文章"
  echo ""
  echo "  ${BOLD}版本管理${RESET}:"
  echo "    python3 scripts/bump_version.py            # 交互式升级"
  echo "    python3 scripts/bump_version.py minor     # 小版本升级"
  echo "    python3 scripts/bump_version.py patch     # 补丁版本升级"
  echo ""
  echo "  ${BOLD}升级${RESET}:"
  echo "    cd $PLUGIN_ROOT && git pull && bash install.sh"
  echo ""
  echo "  ${BOLD}卸载${RESET}:"
  echo "    rm -rf $PLUGIN_ROOT"
  echo ""
}

# =============================================================================
# 主流程
# =============================================================================
main() {
  header

  echo "  插件目录: $PLUGIN_ROOT"
  echo ""

  # 1. 系统依赖
  check_system

  # 2. Python 依赖
  install_python_deps || true

  # 3. Playwright（截图渲染）
  install_playwright || true

  # 4. PicGo
  install_picgo || true

  # 5. yt-dlp（可选）
  install_ytdlp || true

  # 6. NotebookLM CLI（可选）
  install_notebooklm_cli || true

  # 7. MINIMAX API Key
  config_minimax_key || true

  # 8. GEMINI API Key（可选）
  config_gemini_key || true

  # 9. 验证
  verify

  # 10. 使用说明
  usage
}

main "$@"
