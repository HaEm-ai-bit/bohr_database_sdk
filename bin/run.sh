#!/bin/bash
#
# 分库上传脚本 — 按数据库分类顺序执行
#
# 用法：
#   bash bin/run.sh          # 上传全部4个库
#   bash bin/run.sh nano     # 只上传纳米酶库
#   bash bin/run.sh bio      # 只上传生物反应库
#   bash bin/run.sh enzy     # 只上传酶库
#   bash bin/run.sh metabolite # 只上传代谢物库

BASE="/share/allpdfs/bohr_database_sdk"
SCRIPT="$BASE/scripts/upload.py"
TIMEOUT="${CLIENT_TIMEOUT:-120}"

if [ -z "$BOHR_ACCESS_KEY" ]; then
    echo "❌ 请先设置环境变量 BOHR_ACCESS_KEY"
    echo "   export BOHR_ACCESS_KEY=<your_access_key>"
    exit 1
fi

run_nano() {
    echo "========================================"
    echo "1) 纳米酶库（ID: 878qb，8 张表）"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$SCRIPT" \
        -k "878qb" -b "$BASE/configs/nano.json" \
        --batch-size 5000 --skip-exists
}

run_metabolite() {
    echo "========================================"
    echo "2) 代谢物库（ID: 351de，1 张表）"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$SCRIPT" \
        -k "351de" -b "$BASE/configs/metabolite.json" \
        --batch-size 2000 --skip-exists
}

run_enzy() {
    echo "========================================"
    echo "3) 酶库（ID: 555fu，3 张表）"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$SCRIPT" \
        -k "555fu" -b "$BASE/configs/enzy.json" \
        --batch-size 5000 --skip-exists
}

run_bio() {
    echo "========================================"
    echo "4) 生物反应库（ID: 531km，10 张表）"
    echo "   --inf-replace 处理表9中的 inf 值"
    echo "========================================"
    CLIENT_TIMEOUT=$TIMEOUT python3 "$SCRIPT" \
        -k "531km" -b "$BASE/configs/bio.json" \
        --batch-size 5000 --skip-exists --inf-replace
}

case "${1:-all}" in
    nano)       run_nano ;;
    metabolite) run_metabolite ;;
    enzy)       run_enzy ;;
    bio)        run_bio ;;
    all)        run_nano; run_metabolite; run_enzy; run_bio ;;
    *)
        echo "用法: bash bin/run.sh [nano|metabolite|enzy|bio|all]"
        exit 1 ;;
esac

echo ""
echo "✅ 完成"
