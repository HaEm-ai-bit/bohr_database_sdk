import os
import json
import pandas as pd
import argparse
from bohrium_open_sdk import OpenSDK
from bohrium_open_sdk.db import Tiefblue, SQLClient, TableExt

# ========== 1. 固定初始化部分（永久复用） ==========
# 基础配置（通过环境变量 BOHR_ACCESS_KEY 传入，不在代码中硬编码）
MAIN_ACCESS_KEY = os.environ.get("BOHR_ACCESS_KEY", "")
if not MAIN_ACCESS_KEY:
    raise SystemExit(
        "❌ 环境变量 BOHR_ACCESS_KEY 未设置，请先执行：\n"
        "   export BOHR_ACCESS_KEY=<your_access_key>"
    )
AppKey = ""
BaseUrl = "https://openapi.dp.tech"
TiefBlueUrl = "https://tiefblue.dp.tech"

# 初始化所有客户端（超时时间60秒，适配大数据传输）
sdk_client = OpenSDK(
    access_key=MAIN_ACCESS_KEY,
    app_key=AppKey,
    base_url=BaseUrl,
    timeout=os.environ.get("CLIENT_TIMEOUT", 60)
)
tiefblue_client = Tiefblue(
    access_key=MAIN_ACCESS_KEY,
    app_key=AppKey,
    base_url=BaseUrl,
    tiefblue_url=TiefBlueUrl,
    timeout=os.environ.get("CLIENT_TIMEOUT", 60)
)
database_client = SQLClient(
    access_key=MAIN_ACCESS_KEY,
    app_key=AppKey,
    openapi_addr=BaseUrl,
    timeout=os.environ.get("CLIENT_TIMEOUT", 60)
)
print("✅ SDK客户端初始化完成")

# ========== 2. Excel读取生成表结构Schema ==========
def excel_to_table_schema(file_path, sheet_name=None):
    """
    读取Excel指定sheet，生成符合AlterTable要求的表结构Schema列表
    :param file_path: Excel文件路径
    :param sheet_name: sheet名称（None则读取第一个sheet）
    :return: 表结构列表（直接传给AlterTable接口）
    """
    # 1. 读取Excel（指定sheet名称，默认第一个）
    try:
        if sheet_name is None:
            df = pd.read_excel(file_path, sheet_name=0)  # 默认第一个sheet
        else:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
    except Exception as e:
        raise ValueError(f"读取Excel失败：{str(e)}（检查文件路径/sheet名称是否正确）")

    # 2. 模糊匹配核心列（适配Excel列名：字段名/数据类型/描述）
    def match_column(df, keywords):
        for col in df.columns:
            col_str = str(col).strip()
            if any(kw in col_str for kw in keywords):
                return col
        return None

    title_col = match_column(df, ["字段名", "Column", "列名"])
    data_type_col = match_column(df, ["数据类型", "Type", "类型"])
    desc_col = match_column(df, ["描述", "Description", "含义"])

    # 检查必要列是否存在
    if not all([title_col, data_type_col, desc_col]):
        missing = []
        if not title_col: missing.append("字段名（字段名/Column/列名）")
        if not data_type_col: missing.append("数据类型（数据类型/Type/类型）")
        if not desc_col: missing.append("描述（描述/Description/含义）")
        raise ValueError(f"Excel缺少必要列：{', '.join(missing)}")

    # 3. 数据类型映射（严格匹配接口要求）
    type_mapping = {
        "string": "str",
        "str": "str",
        "float": "num",
        "int": "num",
        "number": "num",
        "num": "num",
        "smiles": "smiles"
    }

    # 4. 生成Schema列表（与AlterTable接口格式一致）
    schema_list = []
    for _, row in df.iterrows():
        # 提取字段名（保留原始格式）
        title = str(row[title_col]).strip() if pd.notna(row[title_col]) else ""
        if not title:
            continue  # 跳过空字段名
        
        # 转换数据类型
        raw_type = str(row[data_type_col]).strip().lower() if pd.notna(row[data_type_col]) else "str"
        data_type = type_mapping.get(raw_type, "str")
        
        # 提取描述
        description = str(row[desc_col]).strip() if pd.notna(row[desc_col]) else ""

        schema_list.append({
            "title": title,
            "dataType": data_type,
            "description": description
        })

    if not schema_list:
        raise ValueError("Excel中未提取到有效字段（所有字段名均为空）")
    
    return schema_list


# ========== 2.2 CSV 读取生成表结构 Schema（与 maintaining_field_descriptions 下 CSV 格式一致）==========
def csv_to_table_schema(csv_path, encoding_list=("utf-8-sig", "utf-8", "gbk", "gb2312")):
    """
    从 CSV 字段描述文件读取，生成符合 AlterTable 要求的表结构 Schema 列表。
    与 maintaining_field_descriptions/ 下各 CSV 格式一致：字段名, 数据类型, 描述（或含义）
    :param csv_path: CSV 文件路径
    :param encoding_list: 尝试的编码列表
    :return: 表结构列表（直接传给 AlterTable 接口）
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV 文件不存在：{csv_path}")

    df = None
    used_encoding = None
    for enc in encoding_list:
        try:
            df = pd.read_csv(csv_path, encoding=enc)
            used_encoding = enc
            break
        except Exception:
            continue
    if df is None:
        raise RuntimeError(f"无法读取 CSV，尝试的编码：{list(encoding_list)}")

    # 列名匹配：字段名 / 数据类型 / 描述 或 含义
    def match_column(df, keywords):
        for col in df.columns:
            col_str = str(col).strip()
            if any(kw in col_str for kw in keywords):
                return col
        return None

    title_col = match_column(df, ["字段名", "Column", "列名"])
    data_type_col = match_column(df, ["数据类型", "Type", "类型"])
    desc_col = match_column(df, ["描述", "Description", "含义"])

    if not all([title_col, data_type_col]):
        missing = []
        if not title_col: missing.append("字段名")
        if not data_type_col: missing.append("数据类型")
        raise ValueError(f"CSV 缺少必要列：{', '.join(missing)}（描述/含义可选）")
    if not desc_col:
        desc_col = None  # 描述可选，没有则用空字符串

    type_mapping = {
        "string": "str", "str": "str", "text": "str",
        "float": "num", "int": "num", "number": "num", "num": "num",
        "smiles": "smiles"
    }

    schema_list = []
    for _, row in df.iterrows():
        title = str(row[title_col]).strip() if pd.notna(row[title_col]) else ""
        if not title:
            continue
        raw_type = str(row[data_type_col]).strip().lower() if pd.notna(row[data_type_col]) else "str"
        data_type = type_mapping.get(raw_type, "str")
        description = str(row[desc_col]).strip() if desc_col and pd.notna(row.get(desc_col)) else ""

        schema_list.append({
            "title": title,
            "dataType": data_type,
            "description": description
        })

    if not schema_list:
        raise ValueError("CSV 中未提取到有效字段（所有字段名均为空）")

    print(f"✅ CSV 读取成功，编码：{used_encoding}，共 {len(schema_list)} 个字段")
    return schema_list


# ========== 3. 更新表结构接口 ==========
def update_table_schema(table_ak, schema):
    """
    调用AlterTable接口更新表结构
    :param table_ak: 目标表的AccessKey
    :param schema: 表结构列表（excel_to_table_schema生成）
    :return: 接口返回结果
    """
    try:
        result = database_client.table_with_ak(table_ak).AlterTable(schema)
        print(f"\n✅ 表[{table_ak}]结构更新成功！")
        return result
    except Exception as e:
        raise RuntimeError(f"表[{table_ak}]结构更新失败：{str(e)}")

# ========== 4. 命令行主逻辑 ==========
if __name__ == "__main__":
    # 初始化命令行参数解析器
    parser = argparse.ArgumentParser(
        description="从 CSV 或 Excel 读取字段描述，更新 Bohr 平台指定表的表结构（AlterTable）"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-c", "--csv",
        type=str,
        help="字段描述 CSV 路径（与 maintaining_field_descriptions/ 下格式一致）"
    )
    group.add_argument(
        "-f", "--file",
        type=str,
        help="Excel 文件路径（含字段名、数据类型、描述等列）"
    )
    parser.add_argument(
        "-s", "--sheet",
        type=str,
        required=False,
        default=None,
        help="Excel sheet名称（可选，例如：4；不填则读取第一个sheet）"
    )
    parser.add_argument(
        "-ak", "--target-table-ak",
        dest="target_table_ak",  # 参数别名，方便代码中调用
        type=str,
        required=True,
        help="目标表的AccessKey（必填，例如：351de04）"
    )

    # 解析参数
    args = parser.parse_args()

    try:
        if args.csv:
            print(f"📌 从 CSV 读取表结构：{args.csv}")
            table_schema = csv_to_table_schema(args.csv)
        else:
            print(f"📌 从 Excel 读取表结构：{args.file} (sheet: {args.sheet or '第一个'})")
            table_schema = excel_to_table_schema(args.file, args.sheet)
            print(f"✅ Excel 读取完成，共 {len(table_schema)} 个字段")

        print(f"\n📌 正在更新表 [{args.target_table_ak}] 结构...")
        update_result = update_table_schema(args.target_table_ak, table_schema)
        print("\n📊 更新结果详情：")
        print(json.dumps(update_result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"\n❌ 执行失败：{str(e)}")
        exit(1)