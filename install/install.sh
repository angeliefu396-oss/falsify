#!/usr/bin/env sh
# 把 falsify 安装到 Agent Skills 目录。
#
#   sh install/install.sh                 自动探测并安装到所有已存在的 skills 目录
#   sh install/install.sh ~/some/skills   装到指定目录（会创建 <dest>/falsify）
#   sh install/install.sh --en            英文入口：SKILL.en.md 复制成 SKILL.md
#   sh install/install.sh --check         只报告会装到哪里
#   sh install/install.sh --remove        从已安装位置移除
set -eu

NAME="falsify"
SRC="$(cd "$(dirname "$0")/.." && pwd)"

candidates() {
  echo "$HOME/.claude/skills"
  echo "$HOME/.dsh/skills"
  echo "$HOME/.config/opencode/skills"
  echo "$HOME/.codex/skills"
  echo "$HOME/.cursor/skills"
}

exists_dirs() {
  candidates | while IFS= read -r d; do
    if [ -d "$d" ]; then echo "$d"; fi
  done
  return 0
}

REMOVE=0
CHECK=0
EN=0
TARGET=""
for arg in "$@"; do
  case "$arg" in
    --remove) REMOVE=1 ;;
    --check) CHECK=1 ;;
    --en|--lang-en) EN=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) TARGET="$arg" ;;
  esac
done

if [ -n "$TARGET" ]; then
  DEST_DIRS="$TARGET"
else
  DEST_DIRS="$(exists_dirs || true)"
  if [ -z "$DEST_DIRS" ]; then
    DEST_DIRS="$HOME/.claude/skills"
    if [ "$CHECK" -eq 0 ]; then
      mkdir -p "$DEST_DIRS"
      echo "未发现已有 skills 目录，创建 $DEST_DIRS"
    fi
  fi
fi

for base in $DEST_DIRS; do
  dest="$base/$NAME"
  if [ "$REMOVE" -eq 1 ]; then
    if [ -d "$dest" ]; then rm -rf "$dest"; echo "已移除 $dest"; else echo "未安装：$dest"; fi
    continue
  fi
  if [ "$CHECK" -eq 1 ]; then
    if [ "$EN" -eq 1 ]; then echo "将安装到 $dest（英文入口）"; else echo "将安装到 $dest"; fi
    continue
  fi
  mkdir -p "$base"
  rm -rf "$dest"
  cp -R "$SRC" "$dest"
  rm -rf "$dest/.git" "$dest/tests/scratch" "$dest/__pycache__" "$dest/scripts/__pycache__" "$dest/tests/__pycache__"
  if [ "$EN" -eq 1 ]; then
    cp "$dest/SKILL.en.md" "$dest/SKILL.md"
    echo "已安装 $dest（英文入口：SKILL.en.md → SKILL.md）"
  else
    echo "已安装 $dest"
  fi
done

if [ "$REMOVE" -eq 0 ] && [ "$CHECK" -eq 0 ]; then
  echo
  echo "新开一个 agent 会话后生效（skills 目录通常在会话启动时扫描）。"
  echo "验证：问「请加载 证伪内核，只确认版本和核心工作方式。」"
fi
