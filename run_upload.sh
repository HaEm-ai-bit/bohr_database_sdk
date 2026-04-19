#!/bin/bash
#
# 分类上传脚本 —— 按数据库分库顺序执行
#
# 流程以 分类上传命令.md 为准，各库 AK 已内置，按需取消注释执行。
#
# 使用方法：
#   bash run_upload.sh          # 执行所有库（4个）
#   bash run_upload.sh nano     # 只执行纳米酶库
#   bash run_upload.sh bio      # 只执行生物反应库
#   bash run_upload.sh enzy     # 只执行酶库
#   bash run_upload.sh metabolite # 只执行代谢物库

BASE="/share/allpdfs/bohr_database_sdk"
TIMEOUT="${CLIENT_TIMEOUT:-120}"

# ========== 主账号 AccessKey ==========
# 方式1（推荐）：提前在 shell 中设置：export BOHR_ACCESS_KEY=xxxxxxxx
# 方式2：直接在下一行填写（仅限本地使用，勿提交到 git）
# export BOHR_ACCESS_KEY="请填写你的主账号AccessKey"

if [ -z "$BOHR_ACCESS_KEY" ]; then
    echo "❌ 错误：请先设置环境变量 BOHR_ACCESS_KEY"
    echo "   export BOHR_ACCESS_KEY=<your_access_key>"
    exit 1
fi

run_nano() {
    echo "========================================"
    echo "1) 纳米酶库（ID: 878qb，8 张表）"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$BASE/upload_database_tables_omit_empty.py" \
        -k "878qb" \
        -b "$BASE/nano_only.json" \
        --batch-size 5000 \
        --skip-exists
}

run_metabolite() {
    echo "========================================"
    echo "2) 代谢物库（ID: 351de，1 张表）"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$BASE/upload_database_tables_omit_empty.py" \
        -k "351de" \
        -b "$BASE/metabolite_only.json" \
        --batch-size 2000 \
        --skip-exists
}

run_enzy() {
    echo "========================================"
    echo "3) 酶库（ID: 555fu，3 张表）"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$BASE/upload_database_tables_omit_empty.py" \
        -k "555fu" \
        -b "$BASE/enzy_only.json" \
        --batch-size 5000 \
        --skip-exists
}

run_bio() {
    echo "========================================"
    echo "4) 生物反应库（ID: 531km，10 张表）"
    echo "   注意：--inf-replace 处理表9中的 inf 值"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$BASE/upload_database_tables_omit_empty.py" \
        -k "531km" \
        -b "$BASE/bio_only.json" \
        --batch-size 5000 \
        --skip-exists \
        --inf-replace
}

# ========== 入口 ==========
TARGET="${1:-all}"

case "$TARGET" in
    nano)       run_nano ;;
    metabolite) run_metabolite ;;
    enzy)       run_enzy ;;
    bio)        run_bio ;;
    all)
        run_nano
        run_metabolite
        run_enzy
        run_bio
        ;;
    *)
        echo "用法: bash run_upload.sh [nano|metabolite|enzy|bio|all]"
        exit 1
        ;;
esac

echo ""
echo "✅ 完成"
