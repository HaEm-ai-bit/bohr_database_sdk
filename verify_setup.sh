#!/bin/bash
#
# 环境验证脚本 —— 检查最新版上传流程所需文件是否就绪
#

BASE="/share/allpdfs/bohr_database_sdk"
PASS=0
FAIL=0

ok()   { echo "✅ $*"; PASS=$((PASS+1)); }
fail() { echo "❌ $*"; FAIL=$((FAIL+1)); }
warn() { echo "⚠️  $*"; }

echo "========================================"
echo "配置文件验证（最新流程）"
echo "========================================"

# ---------- 上传脚本 ----------
echo ""
echo "【上传脚本】"
[ -f "$BASE/upload_database_tables_omit_empty.py" ] \
    && ok "upload_database_tables_omit_empty.py 存在" \
    || fail "upload_database_tables_omit_empty.py 缺失"

# ---------- 分类配置 JSON ----------
echo ""
echo "【分类配置 JSON】"
for cfg in nano_only.json metabolite_only.json enzy_only.json bio_only.json; do
    if [ -f "$BASE/$cfg" ]; then
        if python3 -c "import json; json.load(open('$BASE/$cfg'))" 2>/dev/null; then
            COUNT=$(python3 -c "import json; print(len(json.load(open('$BASE/$cfg'))['tables']))")
            ok "$cfg — $COUNT 张表"
        else
            fail "$cfg JSON 格式错误"
        fi
    else
        fail "$cfg 缺失"
    fi
done

# ---------- 运行脚本 ----------
echo ""
echo "【Shell 运行脚本】"
for sh in run_upload.sh run_upload_single.sh; do
    if [ -f "$BASE/$sh" ]; then
        ok "$sh 存在"
        [ -x "$BASE/$sh" ] || warn "$sh 不可执行（chmod +x $BASE/$sh）"
    else
        fail "$sh 缺失"
    fi
done

# ---------- 字段描述 CSV ----------
echo ""
echo "【字段描述文件（maintaining_field_descriptions）】"

check_desc() {
    local label=$1 dir=$2 expected=$3
    if [ -d "$dir" ]; then
        local cnt
        cnt=$(ls "$dir"/*.csv 2>/dev/null | wc -l)
        [ "$cnt" -eq "$expected" ] \
            && ok "$label: $cnt 个 CSV" \
            || { ok "$label: $cnt 个 CSV"; warn "预期 $expected 个，请确认"; }
    else
        fail "$label 目录不存在: $dir"
    fi
}

check_desc "代谢物库" "$BASE/maintaining_field_descriptions/metabolite" 1
check_desc "酶库"     "$BASE/maintaining_field_descriptions/enzy"       3
check_desc "生物反应库" "$BASE/maintaining_field_descriptions/bio"      10
check_desc "纳米酶库" "$BASE/maintaining_field_descriptions/nano"        8

# ---------- 数据文件目录 ----------
echo ""
echo "【数据文件目录】"

DATA_ROOT="/share/allpdfs/final_bioreaction_extraction_database"

check_data() {
    local label=$1 dir=$2 expected=$3
    if [ -d "$dir" ]; then
        local cnt
        cnt=$(ls "$dir"/*.csv 2>/dev/null | wc -l)
        ok "$label: $cnt 个 CSV（预期 $expected）"
        [ "$cnt" -lt "$expected" ] && warn "文件数量偏少，请确认"
    else
        fail "$label 目录不存在: $dir"
    fi
}

check_data "代谢物库" "$DATA_ROOT/1.metabolite_database"  1
check_data "酶库"     "$DATA_ROOT/2.enzyme_database"       3
check_data "生物反应库" "$DATA_ROOT/3.bioreaction_database" 10
check_data "纳米酶库" "$DATA_ROOT/4.nanozyme_database"      8

# ---------- Python 依赖 ----------
echo ""
echo "【Python 依赖】"
python3 -c "import bohrium_open_sdk" 2>/dev/null \
    && ok "bohrium_open_sdk 已安装" \
    || fail "bohrium_open_sdk 未安装（pip3 install bohrium_open_sdk）"

python3 -c "import pandas" 2>/dev/null \
    && ok "pandas 已安装" \
    || fail "pandas 未安装（pip3 install pandas）"

# ---------- 汇总 ----------
echo ""
echo "========================================"
echo "验证完成：✅ $PASS 项通过  ❌ $FAIL 项失败"
echo "========================================"
echo ""
if [ $FAIL -eq 0 ]; then
    echo "下一步：bash $BASE/run_upload.sh [nano|metabolite|enzy|bio|all]"
else
    echo "请先修复上述失败项，再执行上传。"
fi
echo ""
