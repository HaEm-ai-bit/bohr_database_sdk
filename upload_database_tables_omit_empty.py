#!/usr/bin/env python3
"""
数据库表批量上传到 Bohr SDK 的通用标准化脚本

功能：
1. 从CSV字段描述文件读取表结构
2. 创建新表
3. 从数据库CSV文件读取数据并批量插入

空列处理：CSV 列为空时不写该字段名（不传该键），前端无此字段则展示 null，避免被展示为 0。

inf 处理（--inf-replace）：
  bio 表9数据含 inf 值，JSON 序列化会输出非标准 Infinity，接口会报错。
  加 --inf-replace 后，仅对数值列（dataType=num）将 inf/-inf 替换为 ±1e30。

支持的数据库：
- 1.metabolite_database
- 2.enzyme_database
- 3.bioreaction_database（bio 库需加 --inf-replace）
- 4.nanozyme_database
"""

import os
import csv
import json
import math
import pandas as pd
import argparse
from pathlib import Path
from bohrium_open_sdk import OpenSDK
from bohrium_open_sdk.db import Tiefblue, SQLClient, TableExt

# ========== 全局配置 ==========
MAIN_ACCESS_KEY = os.environ.get("BOHR_ACCESS_KEY", "")
if not MAIN_ACCESS_KEY:
    raise SystemExit(
        "❌ 环境变量 BOHR_ACCESS_KEY 未设置，请先执行：\n"
        "   export BOHR_ACCESS_KEY=<your_access_key>"
    )
AppKey = ""
BaseUrl = "https://openapi.dp.tech"
TiefBlueUrl = "https://tiefblue.dp.tech"

# 初始化SDK客户端
sdk_client = OpenSDK(
    access_key=MAIN_ACCESS_KEY,
    app_key=AppKey,
    base_url=BaseUrl,
    timeout=int(os.environ.get("CLIENT_TIMEOUT", 120))
)
database_client = SQLClient(
    access_key=MAIN_ACCESS_KEY,
    app_key=AppKey,
    openapi_addr=BaseUrl,
    timeout=int(os.environ.get("CLIENT_TIMEOUT", 120))
)
print("✅ SDK客户端初始化完成")


# ========== 核心函数 ==========
def csv_description_to_schema(csv_desc_path):
    """
    从CSV字段描述文件读取表结构
    :param csv_desc_path: CSV描述文件路径
    :return: 表结构schema列表
    """
    try:
        df = pd.read_csv(csv_desc_path)
        print(f"✅ 成功读取字段描述文件：{csv_desc_path}")
    except Exception as e:
        raise ValueError(f"读取CSV描述文件失败：{str(e)}")
    
    # 检查必要列（描述列可用「描述」或「含义」）
    required_cols = ['字段名', '数据类型']
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV描述文件缺少必要列：{missing_cols}")
    desc_col = '描述' if '描述' in df.columns else ('含义' if '含义' in df.columns else None)
    if desc_col is None:
        raise ValueError("CSV描述文件缺少描述列（需「描述」或「含义」之一）")

    # 生成schema
    table_schema = []
    for _, row in df.iterrows():
        field_name = str(row['字段名']).strip() if pd.notna(row['字段名']) else ""
        if not field_name:
            continue
        
        data_type = str(row['数据类型']).strip().lower() if pd.notna(row['数据类型']) else "str"
        description = str(row[desc_col]).strip() if pd.notna(row[desc_col]) else ""
        
        # 数据类型映射
        type_mapping = {
            'str': 'str', 'string': 'str', 'text': 'str',
            'num': 'num', 'number': 'num', 'int': 'num', 'float': 'num',
            'smiles': 'smiles'
        }
        final_type = type_mapping.get(data_type, 'str')
        
        table_schema.append({
            "title": field_name,
            "dataType": final_type,
            "description": description
        })
    
    print(f"✅ 从CSV描述文件提取 {len(table_schema)} 个字段")
    return table_schema


def create_table(db_ak, table_name, schema, header_rows=1):
    """
    创建新表
    :param db_ak: 数据库AK
    :param table_name: 表名称
    :param schema: 表结构
    :param header_rows: 表头行数
    :return: table_ak
    """
    try:
        table_ak = database_client.db_with_ak(db_ak).CreateTableV2(
            name=table_name,
            header_rows=header_rows,
            schema=schema
        )
        print(f"\n✅ 新表 [{table_name}] 创建成功！table_ak = {table_ak}")
        return table_ak
    except Exception as e:
        if "TABLE_NAME_ALREADY_EXIST" in str(e):
            print(f"\n⚠️  表名 [{table_name}] 已存在，跳过创建")
            return None
        else:
            raise RuntimeError(f"创建表失败：{e}")


# inf 替换常量（--inf-replace 模式下使用，避免 JSON 序列化出 Infinity 导致接口报错）
_INF_POS = 1e30
_INF_NEG = -1e30


def _numeric_inf_replacement(v):
    """
    仅用于数值列：若值为 inf/Infinity 返回替代数值，否则返回 None。
    """
    if v is None or v == "" or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ('inf', 'infinity'):
            return _INF_POS
        if s in ('-inf', '-infinity'):
            return _INF_NEG
        return None
    try:
        f = float(v)
        if math.isinf(f):
            return _INF_NEG if f < 0 else _INF_POS
    except (TypeError, ValueError):
        pass
    return None


def csv_to_json_data(csv_path, numeric_columns=None, encoding_list=['utf-8-sig', 'utf-8', 'gbk', 'gb2312']):
    """
    读取CSV数据文件并转换为JSON格式。
    空列不写该字段名；若传入 numeric_columns，则对数值列中的 inf/-inf 替换为 ±1e30（不删键）。
    :param csv_path: CSV数据文件路径
    :param numeric_columns: 数值列名集合（dataType=num），传入时启用 inf 替换；None 表示不替换
    :param encoding_list: 尝试的编码列表
    :return: (数据列表, 列名列表)
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV数据文件不存在：{csv_path}")
    
    for encoding in encoding_list:
        try:
            df = pd.read_csv(csv_path, encoding=encoding, low_memory=False)
            print(f"✅ CSV数据文件读取成功，使用编码：{encoding}")
            print(f"   数据行数：{len(df)}, 列数：{len(df.columns)}")
            
            data_list = df.to_dict('records')
            columns = df.columns.tolist()
            
            # 清理数据：空列删键；数值列中的 inf 替换为大数值（不删键）
            for row in data_list:
                keys_to_del = [k for k, v in row.items() if pd.isna(v) or v == ""]
                for k in keys_to_del:
                    del row[k]
                if numeric_columns:
                    for k in list(row.keys()):
                        if k not in numeric_columns:
                            continue
                        replacement = _numeric_inf_replacement(row[k])
                        if replacement is not None:
                            row[k] = replacement
            
            return data_list, columns
        except Exception:
            continue
    
    raise RuntimeError(f"无法读取CSV文件，尝试的编码：{encoding_list}")


def insert_data_batch(table_ak, data, batch_size=5000):
    """
    分批插入数据
    :param table_ak: 目标表AK
    :param data: 数据列表
    :param batch_size: 每批数量
    :return: 成功插入数量
    """
    total_count = len(data)
    if total_count == 0:
        print("⚠️  无数据可插入")
        return 0
    
    success_count = 0
    fail_batches = []
    total_batches = (total_count + batch_size - 1) // batch_size
    
    print(f"\n📊 开始分批插入：共 {total_count} 条数据，分 {total_batches} 批，每批 {batch_size} 条")
    
    for batch_idx in range(total_batches):
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, total_count)
        batch_data = data[start_idx:end_idx]
        batch_num = batch_idx + 1
        
        print(f"🔄 正在插入第 {batch_num}/{total_batches} 批（{start_idx+1}-{end_idx} 条）")
        
        try:
            result = database_client.table_with_ak(table_ak).Insert(batch_data)
            success_count += len(batch_data)
            print(f"   ✅ 成功插入 {len(batch_data)} 条")
        except Exception as e:
            print(f"   ❌ 第 {batch_num} 批插入失败：{e}")
            fail_batches.append(batch_num)
    
    print(f"\n✅ 分批插入完成！总计 {total_count} 条，成功 {success_count} 条")
    if fail_batches:
        print(f"❌ 失败批次：{fail_batches}")
    
    return success_count


def check_column_match(schema_columns, csv_columns):
    """
    检查CSV列名与表结构列名是否匹配
    :param schema_columns: 表结构列名列表
    :param csv_columns: CSV列名列表
    """
    def clean_col(col):
        return str(col).strip().lower()
    
    schema_clean = set([clean_col(col) for col in schema_columns])
    csv_clean = set([clean_col(col) for col in csv_columns])
    
    missing = schema_clean - csv_clean
    extra = csv_clean - schema_clean
    
    if not missing and not extra:
        print(f"✅ 列名校验通过！共 {len(schema_clean)} 个字段完全匹配")
        return True
    
    error_msg = "\n💥 列名不匹配！\n"
    if missing:
        error_msg += f"❌ 表结构有但CSV缺失：{[c for c in schema_columns if clean_col(c) in missing]}\n"
    if extra:
        error_msg += f"❌ CSV有但表结构缺失：{[c for c in csv_columns if clean_col(c) in extra]}\n"
    
    raise RuntimeError(error_msg)


def upload_table(db_ak, csv_desc_path, csv_data_path, table_name, batch_size=5000, skip_if_exists=False, inf_replace=False):
    """
    完整的上传流程：创建表 + 插入数据
    :param db_ak: 数据库AK
    :param csv_desc_path: CSV字段描述文件路径
    :param csv_data_path: CSV数据文件路径
    :param table_name: 表名称
    :param batch_size: 批量大小
    :param skip_if_exists: 如果表已存在是否跳过
    :param inf_replace: 是否将数值列中的 inf/-inf 替换为 ±1e30（bio 库表9需要开启）
    :return: (table_ak, inserted_count)
    """
    try:
        print(f"\n{'='*80}")
        print(f"开始处理表：{table_name}")
        print(f"{'='*80}")
        
        # 步骤1：读取表结构
        schema = csv_description_to_schema(csv_desc_path)
        schema_columns = [item['title'] for item in schema]
        
        # 步骤2：创建表
        table_ak = create_table(db_ak, table_name, schema)
        if table_ak is None and skip_if_exists:
            print(f"⏭️  表已存在，跳过数据插入")
            return None, 0
        elif table_ak is None:
            raise RuntimeError("表创建失败且未设置跳过")
        
        # 步骤3：读取数据（空列不写字段名；inf_replace 模式下数值列 inf→±1e30）
        numeric_columns = {item['title'] for item in schema if item.get('dataType') == 'num'} if inf_replace else None
        data_list, csv_columns = csv_to_json_data(csv_data_path, numeric_columns=numeric_columns)
        
        # 步骤4：列名校验
        check_column_match(schema_columns, csv_columns)
        
        # 步骤5：分批插入
        inserted = insert_data_batch(table_ak, data_list, batch_size)
        
        print(f"\n🎉 表 [{table_name}] 处理完成！")
        print(f"   Table AK: {table_ak}")
        print(f"   插入数据：{inserted}/{len(data_list)} 条")
        
        return table_ak, inserted
        
    except Exception as e:
        print(f"\n❌ 处理表 [{table_name}] 失败：{e}")
        return None, 0


# ========== 命令行接口 ==========
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="标准化数据库表上传脚本（空列不写字段名）- 支持单表或批量上传"
    )
    
    # 基础参数
    parser.add_argument(
        "-k", "--db-ak",
        required=True,
        help="数据库AccessKey（必填）"
    )
    
    # 单表上传参数
    parser.add_argument(
        "-d", "--desc",
        help="CSV字段描述文件路径（单表模式必填）"
    )
    parser.add_argument(
        "-c", "--csv",
        help="CSV数据文件路径（单表模式必填）"
    )
    parser.add_argument(
        "-t", "--table-name",
        help="表名称（单表模式必填）"
    )
    
    # 批量上传参数
    parser.add_argument(
        "-b", "--batch-config",
        help="批量配置JSON文件路径（批量模式必填）"
    )
    
    # 可选参数
    parser.add_argument(
        "-bs", "--batch-size",
        type=int,
        default=5000,
        help="每批插入数量（默认5000）"
    )
    parser.add_argument(
        "--skip-exists",
        action="store_true",
        help="如果表已存在则跳过"
    )
    parser.add_argument(
        "--inf-replace",
        action="store_true",
        help="将数值列中的 inf/-inf 替换为 ±1e30（bio 库表9含 inf 值时必须开启）"
    )
    
    args = parser.parse_args()
    
    # 判断是单表模式还是批量模式
    if args.batch_config:
        # 批量模式
        inf_flag = "，数值列 inf→±1e30" if args.inf_replace else ""
        print(f"📦 批量上传模式（空列不写字段名{inf_flag}）")
        with open(args.batch_config, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        results = []
        for table_config in config['tables']:
            table_ak, count = upload_table(
                db_ak=args.db_ak,
                csv_desc_path=table_config['desc_file'],
                csv_data_path=table_config['data_file'],
                table_name=table_config['table_name'],
                batch_size=args.batch_size,
                skip_if_exists=args.skip_exists,
                inf_replace=args.inf_replace
            )
            results.append({
                'table_name': table_config['table_name'],
                'table_ak': table_ak,
                'count': count
            })
        
        # 输出汇总
        print(f"\n{'='*80}")
        print("批量上传完成汇总")
        print(f"{'='*80}")
        for r in results:
            status = "✅" if r['table_ak'] else "❌"
            print(f"{status} {r['table_name']}: {r['count']} 条 (AK: {r['table_ak']})")
    
    elif all([args.desc, args.csv, args.table_name]):
        # 单表模式
        inf_flag = "，数值列 inf→±1e30" if args.inf_replace else ""
        print(f"📄 单表上传模式（空列不写字段名{inf_flag}）")
        upload_table(
            db_ak=args.db_ak,
            csv_desc_path=args.desc,
            csv_data_path=args.csv,
            table_name=args.table_name,
            batch_size=args.batch_size,
            skip_if_exists=args.skip_exists,
            inf_replace=args.inf_replace
        )
    
    else:
        parser.error("请指定单表模式参数（-d, -c, -t）或批量模式参数（-b）")
