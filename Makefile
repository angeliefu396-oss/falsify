# DCAI 统一内核 —— 常用命令
# 需要 python3（Windows 上可用 `python` 或 `py -3`）

PY ?= python

.PHONY: help build check test install uninstall clean

help:
	@echo "make build      重新生成 SKILL.md 内核区块与 dist/"
	@echo "make check      校验生成物与真源同步（CI 同款）"
	@echo "make test       跑全部测试"
	@echo "make install    安装到已存在的 skills 目录（见 install/install.sh）"
	@echo "make clean      清掉缓存与测试临时目录"

build:
	$(PY) scripts/build.py

check:
	$(PY) scripts/build.py --check

test:
	$(PY) -m unittest discover -s tests -v

install:
	sh install/install.sh

uninstall:
	sh install/install.sh --remove

clean:
	rm -rf tests/scratch __pycache__ scripts/__pycache__ tests/__pycache__
