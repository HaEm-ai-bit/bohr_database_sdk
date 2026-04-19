#!/bin/bash
#
# 单张表上传示例
# 修改下方变量后执行：bash bin/run_single.sh

BASE="/share/allpdfs/bohr_database_sdk"
SCRIPT="$BASE/scripts/upload.py"

DB_AK="351de"
SCHEMA_FILE="$BASE/schemas/metabolite/metabolite.csv"
DATA_FILE="/share/allpdfs/final_bioreaction_extraction_database/1.metabolite_database/Metabolite_Database_Merged_hmdb_with_organism_filled_formula_final_standardized.csv"
TABLE_NAME="metabolite_database"
BATCH_SIZE=1000
export CLIENT_TIMEOUT=300

if [ -z "$BOHR_ACCESS_KEY" ]; then
    echo "❌ 请先设置环境变量 BOHR_ACCESS_KEY"
    echo "   export BOHR_ACCESS_KEY=<your_access_key>"
    exit 1
fi

echo "========================================"
echo "单表上传：$TABLE_NAME"
echo "========================================"

python3 "$SCRIPT" \
    -k "$DB_AK" \
    -d "$SCHEMA_FILE" \
    -c "$DATA_FILE" \
    -t "$TABLE_NAME" \
    --batch-size "$BATCH_SIZE" \
    --skip-exists

[ $? -eq 0 ] && echo "✅ 上传完成" || { echo "❌ 上传失败"; exit 1; }
