#!/bin/bash
#
# 上传前环境预检脚本

BASE="/share/allpdfs/bohr_database_sdk"
PASS=0
FAIL=0

ok()   { echo "✅ $*"; PASS=$((PASS+1)); }
fail() { echo "❌ $*"; FAIL=$((FAIL+1)); }
warn() { echo "⚠️  $*"; }

echo "========================================"
echo "环境预检"
echo "========================================"

echo ""
echo "【上传脚本】"
[ -f "$BASE/scripts/upload.py" ] \
    && ok "scripts/upload.py 存在" \
    || fail "scripts/upload.py 缺失"

echo ""
echo "【分库配置 JSON】"
for cfg in bio enzy metabolite nano; do
    if [ -f "$BASE/configs/$cfg.json" ]; then
        COUNT=$(python3 -c "import json; print(len(json.load(open('$BASE/configs/$cfg.json'))['tables']))")
        ok "configs/$cfg.json — $COUNT 张表"
    else
        fail "configs/$cfg.json 缺失"
    fi
done

echo ""
echo "【Shell 脚本】"
for sh in run.sh run_single.sh check.sh; do
    if [ -f "$BASE/bin/$sh" ]; then
        ok "bin/$sh 存在"
        [ -x "$BASE/bin/$sh" ] || warn "bin/$sh 不可执行（chmod +x $BASE/bin/$sh）"
    else
        fail "bin/$sh 缺失"
    fi
done

echo ""
echo "【字段描述 CSV（schemas/）】"
check_schema() {
    local label=$1 dir=$2 expected=$3
    if [ -d "$dir" ]; then
        local cnt; cnt=$(ls "$dir"/*.csv 2>/dev/null | wc -l)
        [ "$cnt" -eq "$expected" ] \
            && ok "$label: $cnt 个 CSV" \
            || { ok "$label: $cnt 个 CSV"; warn "预期 $expected 个"; }
    else
        fail "$label 目录不存在: $dir"
    fi
}
check_schema "代谢物库" "$BASE/schemas/metabolite" 1
check_schema "酶库"     "$BASE/schemas/enzy"       3
check_schema "生物反应库" "$BASE/schemas/bio"      10
check_schema "纳米酶库" "$BASE/schemas/nano"        8

echo ""
echo "【数据文件目录】"
DATA_ROOT="/share/allpdfs/final_bioreaction_extraction_database"
check_data() {
    local label=$1 dir=$2 expected=$3
    if [ -d "$dir" ]; then
        local cnt; cnt=$(ls "$dir"/*.csv 2>/dev/null | wc -l)
        ok "$label: $cnt 个 CSV（预期 $expected）"
        [ "$cnt" -lt "$expected" ] && warn "文件数量偏少，请确认"
    else
        fail "$label 目录不存在: $dir"
    fi
}
check_data "代谢物库" "$DATA_ROOT/1.metabolite_database"   1
check_data "酶库"     "$DATA_ROOT/2.enzyme_database"        3
check_data "生物反应库" "$DATA_ROOT/3.bioreaction_database" 10
check_data "纳米酶库" "$DATA_ROOT/4.nanozyme_database"       8

echo ""
echo "【Python 依赖】"
python3 -c "import bohrium_open_sdk" 2>/dev/null \
    && ok "bohrium_open_sdk 已安装" \
    || fail "bohrium_open_sdk 未安装（pip3 install bohrium_open_sdk）"
python3 -c "import pandas" 2>/dev/null \
    && ok "pandas 已安装" \
    || fail "pandas 未安装（pip3 install pandas）"

echo ""
echo "========================================"
echo "预检完成：✅ $PASS 项通过  ❌ $FAIL 项失败"
echo "========================================"
echo ""
[ $FAIL -eq 0 ] \
    && echo "下一步：bash bin/run.sh [nano|metabolite|enzy|bio|all]" \
    || echo "请先修复上述失败项。"
echo ""
