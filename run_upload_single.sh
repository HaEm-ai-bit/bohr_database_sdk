#!/bin/bash
#
# 单表上传示例脚本
# 
# 使用方法：
# bash run_upload_single.sh

# ========== 配置区域 ==========
# 数据库AccessKey（必填）
DB_AK="351de"

# 上传脚本路径
UPLOAD_SCRIPT="/share/allpdfs/bohr_database_sdk/upload_database_tables_omit_empty.py"

# ========== 单表配置示例 ==========
# 字段描述文件
DESC_FILE="/share/allpdfs/bohr_database_sdk/maintaining_field_descriptions/metabolite/metabolite.csv"

# 数据文件
DATA_FILE="/share/allpdfs/final_bioreaction_extraction_database/1.metabolite_database/Metabolite_Database_Merged_hmdb_with_organism_filled_formula_final_standardized.csv"

# 表名称
TABLE_NAME="metabolite_database"

# 批量大小
BATCH_SIZE=1000

# 客户端超时（秒），大表可设为 300
export CLIENT_TIMEOUT=300

# ========== 检查配置 ==========
if [ "$DB_AK" == "请填写你的数据库AK" ]; then
    echo "❌ 错误：请先修改脚本中的 DB_AK 变量"
    exit 1
fi

# ========== 执行上传 ==========
echo "========================================"
echo "单表上传"
echo "========================================"
echo "表名称: $TABLE_NAME"
echo "描述文件: $DESC_FILE"
echo "数据文件: $DATA_FILE"
echo "========================================"
echo ""

python3 "$UPLOAD_SCRIPT" \
    --db-ak "$DB_AK" \
    --desc "$DESC_FILE" \
    --csv "$DATA_FILE" \
    --table-name "$TABLE_NAME" \
    --batch-size "$BATCH_SIZE" \
    --skip-exists

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 上传完成"
else
    echo ""
    echo "❌ 上传失败"
    exit 1
fi
