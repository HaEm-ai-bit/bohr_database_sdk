# ========== 1. 依赖导入 + 全局配置（一次性配置，永久复用） ==========
import os
import csv
import json
import pandas as pd
import argparse
from bohrium_open_sdk import OpenSDK
from bohrium_open_sdk.db import Tiefblue, SQLClient, TableExt

# 基础SDK配置（通过环境变量 BOHR_ACCESS_KEY 传入，不在代码中硬编码）
MAIN_ACCESS_KEY = os.environ.get("BOHR_ACCESS_KEY", "")
if not MAIN_ACCESS_KEY:
    raise SystemExit(
        "❌ 环境变量 BOHR_ACCESS_KEY 未设置，请先执行：\n"
        "   export BOHR_ACCESS_KEY=<your_access_key>"
    )
AppKey = ""
BaseUrl = "https://openapi.dp.tech"
TiefBlueUrl = "https://tiefblue.dp.tech"

# 初始化所有SDK客户端（提升超时时间，适配大数据传输）
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


# ========== 2. 核心工具函数：Excel建表相关（复用原有逻辑，无修改） ==========
def excel_to_table_schema(file_path, sheet_name=0):
    """读取Excel指定sheet，提取字段名/数据类型，生成建表schema"""
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        print(f"✅ 成功读取Excel表结构文件：{file_path}，Sheet：{sheet_name if sheet_name !=0 else '第一个sheet（索引0）'}")
    except Exception as e:
        raise ValueError(f"读取Excel失败：{str(e)}（请检查文件路径/Sheet是否有效，需安装openpyxl）")

    # 模糊匹配列名（字段名/数据类型）
    def match_column(df, target_keywords):
        for col in df.columns:
            col_str = str(col).strip()
            if any(keyword in col_str for keyword in target_keywords):
                return col
        return None

    title_col = match_column(df, ["字段名", "Column", "列名"])
    data_type_col = match_column(df, ["数据类型", "Type", "类型"])

    # 检查必要列
    missing_cols = []
    if not title_col:
        missing_cols.append("字段名（或含“字段名”“Column”的列）")
    if not data_type_col:
        missing_cols.append("数据类型（或含“数据类型”“Type”的列）")
    if missing_cols:
        raise ValueError(f"Excel未找到必要列：{', '.join(missing_cols)}")

    # 数据类型映射
    type_mapping = {
        "string": "str", "str": "str", "字符": "str", "文本": "str", "字符串": "str",
        "num": "num", "number": "num", "int": "num", "float": "num", "数值": "num", "整数": "num", "浮点": "num"
    }

    # 生成schema
    table_schema = []
    for idx, row in df.iterrows():
        original_title = str(row[title_col]).strip() if pd.notna(row[title_col]) else ""
        if not original_title:
            print(f"⚠️  忽略Excel第{idx+2}行：字段名为空")
            continue
        raw_data_type = str(row[data_type_col]).strip().lower() if pd.notna(row[data_type_col]) else "str"
        final_data_type = type_mapping.get(raw_data_type, "str")
        table_schema.append({"title": original_title, "dataType": final_data_type})

    if not table_schema:
        raise ValueError("Excel中未提取到有效字段，无法生成表结构")
    print(f"✅ 从Excel提取{len(table_schema)}个字段，表结构生成完成")
    return table_schema


def create_new_table(db_ak, table_name, header_rows, schema, desc_rows=0, desc_info=None):
    """新建表（CreateTableV2接口），返回table_ak"""
    try:
        ext = TableExt(desc_rows=desc_rows, desc_info=desc_info) if (desc_rows or desc_info) else None
        table_ak = database_client.db_with_ak(db_ak).CreateTableV2(
            name=table_name,
            header_rows=header_rows,
            schema=schema,
            ext=ext
        )
        print(f"\n✅ 新表[{table_name}]创建成功！table_ak = {table_ak}")
        return table_ak
    except Exception as e:
        if "TABLE_NAME_ALREADY_EXIST" in str(e):
            print(f"\n❌ 新建表失败：表名[{table_name}]已存在！请更换表名（如{table_name}_v2）后重新执行")
        else:
            print(f"\n❌ 新建表失败：{e}")
        return None


# ========== 3. 核心工具函数：CSV转JSON + 数据读取（复用原有逻辑，无修改） ==========
def csv_to_universal_json(csv_file_path, json_file_path=None):
    """
    CSV转JSON（自动识别数据类型），可选保存JSON文件
    :param csv_file_path: 输入CSV路径
    :param json_file_path: 输出JSON路径（None则不保存，直接返回数据）
    :return: 转换后的原始数据列表 + 处理后的CSV列名列表
    """
    insert_data = []
    if not os.path.exists(csv_file_path):
        raise FileNotFoundError(f"CSV文件不存在：{csv_file_path}")

    # 定义需要尝试的编码列表，优先utf-8-sig（自动去除BOM）
    encodings = ['utf-8-sig', 'gbk', 'gb2312', 'utf-8']
    csv_file = None
    csv_reader = None
    csv_columns = []

    # 循环尝试编码，直到成功读取（手动控制文件生命周期）
    for encoding in encodings:
        try:
            csv_file = open(csv_file_path, 'r', encoding=encoding)
            csv_reader = csv.DictReader(csv_file)
            csv_columns = csv_reader.fieldnames or []
            next(csv_reader)  # 验证读取
            csv_file.seek(0)
            csv_reader = csv.DictReader(csv_file)
            print(f"✅ CSV文件读取成功，使用编码：{encoding}")
            break
        except (UnicodeDecodeError, LookupError, StopIteration):
            if csv_file:
                csv_file.close()
            continue
        except Exception as e:
            if csv_file:
                csv_file.close()
            continue

    # 所有编码尝试失败
    if not csv_file or not csv_reader or not csv_columns:
        raise RuntimeError(f"CSV文件读取失败！尝试编码：{encodings}，请检查文件格式或编码")

    try:
        if not csv_columns:
            raise ValueError("CSV文件无有效列名，无法转换")

        # 处理每一行数据
        for row_num, row in enumerate(csv_reader, start=1):
            row_data = {}
            for col_name in csv_columns:
                clean_col = col_name.strip()
                cell_value = row[col_name].strip() if row[col_name] else ""
                if not cell_value:
                    row_data[clean_col] = ""
                    continue
                # 自动类型转换
                try:
                    row_data[clean_col] = int(cell_value)
                except ValueError:
                    try:
                        row_data[clean_col] = float(cell_value)
                    except ValueError:
                        row_data[clean_col] = cell_value
            insert_data.append(row_data)

        # 保存JSON（可选）
        if json_file_path:
            os.makedirs(os.path.dirname(json_file_path) or os.getcwd(), exist_ok=True)
            with open(json_file_path, 'w', encoding='utf-8') as json_file:
                json.dump(insert_data, json_file, ensure_ascii=False, indent=2)
            print(f"✅ CSV转JSON完成，文件保存至：{json_file_path}")

        # 清洗列名
        clean_csv_columns = [col.strip() for col in csv_columns]
        print(f"✅ 处理CSV数据完成：共{len(insert_data)}行，有效列名：{clean_csv_columns}")
        return insert_data, clean_csv_columns

    except Exception as e:
        raise RuntimeError(f"CSV转JSON失败：{str(e)}")

    finally:
        # 最终关闭文件（无论成功/失败）
        if csv_file:
            csv_file.close()
            print(f"✅ CSV文件已安全关闭")


# ========== 4. 核心工具函数：分批插入相关（替换为你【验证通过】的完整逻辑，无任何修改） ==========
def insert_data_to_table(table_ak, data):
    """
    向指定数据表插入数据（对应图中Insert接口，你验证通过的核心插入函数）
    :param table_ak: 目标表的AccessKey（如"669ng00"）
    :param data: 要插入的数据列表，格式为[{'字段名1': 值1, '字段名2': 值2, ...}]
    :return: 插入操作的结果
    """
    try:
        # 调用你项目统一的SDK插入接口（已验证正确，无属性错误）
        result = database_client.table_with_ak(table_ak).Insert(data)
        print(f"✅ 单批数据插入表[{table_ak}]成功！插入条数：{len(data)}")
        return result
    except Exception as e:
        print(f"❌ 向表[{table_ak}]插入单批数据失败：{e}")
        return None


def load_data_from_json(json_file_path):
    """
    从JSON文件读取插入数据（格式和insert_data完全一致，兼容单独调用）
    :param json_file_path: JSON文件的路径（比如"my_data.json"）
    :return: 读取到的数据列表，失败返回空列表
    """
    try:
        # 打开并读取JSON文件
        with open(json_file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # 确保读取的是列表（和insert_data格式一致）
        if isinstance(data, list):
            print(f"✅ 成功从{json_file_path}读取到{len(data)}条数据")
            return data
        else:
            print(f"❌ JSON文件格式错误：内容必须是列表（比如 [{...}, {...}]）")
            return []
    except FileNotFoundError:
        print(f"❌ 找不到JSON文件：{json_file_path}（请检查文件路径是否正确）")
        return []
    except json.JSONDecodeError:
        print(f"❌ JSON文件格式错误：请检查文件内容是否符合JSON规范")
        return []
    except Exception as e:
        print(f"❌ 读取JSON文件出错：{e}")
        return []


def batch_insert_data(table_ak, data_list, batch_size=5000):
    """
    分批次插入大量数据（你验证通过的版本，默认5000条/批，含失败批次统计）
    :param table_ak: 目标表AccessKey
    :param data_list: 待插入的总数据列表（CSV转JSON后直接传入，无需额外处理）
    :param batch_size: 每批次插入的条数（默认5000，和你要求一致）
    :return: 总插入成功条数
    """
    total_count = len(data_list)
    success_count = 0
    fail_batches = []

    if total_count == 0:
        print("⚠️ 无数据可插入")
        return 0

    # 计算总批次
    total_batches = (total_count + batch_size - 1) // batch_size
    print(f"\n📊 开始分批次插入：共{total_count}条数据，分{total_batches}批，每批{batch_size}条")

    # 逐批插入
    for batch_idx in range(total_batches):
        # 计算当前批次的起止索引
        start_idx = batch_idx * batch_size
        end_idx = min((batch_idx + 1) * batch_size, total_count)
        batch_data = data_list[start_idx:end_idx]
        batch_num = batch_idx + 1

        print(f"\n🔄 正在插入第{batch_num}/{total_batches}批（{start_idx+1}-{end_idx}条）")
        try:
            # 调用你验证通过的单批插入接口
            result = insert_data_to_table(table_ak, batch_data)
            if result is not None:
                success_count += len(batch_data)
            else:
                fail_batches.append(batch_num)
        except Exception as e:
            print(f"❌ 第{batch_num}批插入异常：{e}")
            fail_batches.append(batch_num)

    # 插入完成汇总
    print(f"\n✅ 分批次插入完成！总计{total_count}条，成功{success_count}条，失败{len(fail_batches)}批")
    if fail_batches:
        print(f"❌ 失败批次：{fail_batches}（可单独重试这些批次）")
    return success_count


# ========== 5. 严格列名校验函数（复用原有逻辑，无修改） ==========
def check_column_match(schema_columns, csv_columns):
    """
    严格校验CSV列名与表结构列名是否匹配
    :param schema_columns: 表结构原始列名列表（从Excel提取）
    :param csv_columns: CSV原始列名列表
    :raise: 列名不匹配则抛出RuntimeError，终止流程
    """
    # 列名清洗：去空格 + 转小写（兼容大小写、首尾空格差异）
    def clean_col(col):
        return col.strip().lower() if col else ""
    
    # 清洗后的列名集合（去重）
    schema_clean = set([clean_col(col) for col in schema_columns])
    csv_clean = set([clean_col(col) for col in csv_columns])
    # 原始列名与清洗后列名的映射（用于打印原始名称）
    schema_col_map = {clean_col(col): col for col in schema_columns}
    csv_col_map = {clean_col(col): col for col in csv_columns}

    # 计算差异：表结构有但CSV缺失的列、CSV有但表结构多余的列
    missing_in_csv = schema_clean - csv_clean  # 必须有，缺失则报错
    extra_in_csv = csv_clean - schema_clean    # 不能有，多余则报错

    # 列名完全匹配，正常返回
    if not missing_in_csv and not extra_in_csv:
        print(f"✅ 列名校验通过！CSV列名与表结构列名完全匹配（共{len(schema_clean)}个字段）")
        return

    # 列名不匹配，构造详细错误信息并抛出异常
    error_msg = "\n💥 列名不匹配，终止数据插入流程！\n"
    if missing_in_csv:
        # 转换为原始表结构列名
        missing_original = [schema_col_map[col] for col in missing_in_csv]
        error_msg += f"❌ 表结构有但CSV文件缺失的字段：{missing_original}\n"
    if extra_in_csv:
        # 转换为原始CSV列名
        extra_original = [csv_col_map[col] for col in extra_in_csv]
        error_msg += f"❌ CSV文件有但表结构多余的字段：{extra_original}\n"
    error_msg += "\n📌 请修正CSV文件列名，保证与表结构完全一致（兼容大小写、首尾空格）！"
    
    # 抛出异常，终止后续所有流程
    raise RuntimeError(error_msg)


# ========== 6. 全流程主函数（复用原有逻辑，调用适配新分批函数，无其他修改） ==========
def auto_create_table_and_insert(db_ak, excel_path, csv_path, table_name, sheet_name=0, header_rows=1,
                                 batch_size=5000, json_save_path=None, desc_rows=0, desc_info=None):
    """
    全流程自动化函数（含严格列名校验，不匹配直接终止）
    :param db_ak: 数据库AK
    :param excel_path: 表结构Excel文件路径
    :param csv_path: 待插入数据CSV文件路径
    :param table_name: 新建表名称
    :param sheet_name: Excel读取的Sheet（默认0）
    :param header_rows: 新建表表头行数（默认1）
    :param batch_size: 分批插入条数（默认5000）
    :param json_save_path: CSV转JSON的保存路径（None则不保存）
    :param desc_rows: 表描述行数（默认0）
    :param desc_info: 表描述信息（默认None）
    :return: (table_ak, total_inserted) 新建表AK + 总插入条数
    """
    try:
        # 步骤1：从Excel提取schema，新建表
        table_schema = excel_to_table_schema(excel_path, sheet_name)
        table_ak = create_new_table(db_ak, table_name, header_rows, table_schema, desc_rows, desc_info)
        if not table_ak:
            raise RuntimeError("新建表失败，终止后续数据插入流程")
        # 提取表结构原始列名
        schema_columns = [item["title"] for item in table_schema]

        # 步骤2：CSV转JSON（自动识别类型），获取数据和原始列名
        insert_data, csv_columns = csv_to_universal_json(csv_path, json_save_path)

        # 步骤3：核心严格校验：列名不匹配直接终止（新增关键步骤）
        check_column_match(schema_columns, csv_columns)

        # 步骤4：调用你验证通过的分批插入函数（参数直接适配，无缝衔接）
        total_inserted = batch_insert_data(table_ak, insert_data, batch_size)

        # 全流程完成提示
        print(f"\n🎉 全流程执行完成！")
        print(f"📌 新建表AK：{table_ak}")
        print(f"📌 表名称：{table_name}")
        print(f"📌 总处理数据：{len(insert_data)}条 | 成功插入：{total_inserted}条")
        if len(insert_data) != total_inserted:
            print(f"⚠️  注意：部分数据插入失败，需检查日志排查失败批次")

        return table_ak, total_inserted

    except Exception as e:
        print(f"\n💥 全流程执行失败：{str(e)}")
        return None, 0


# ========== 7. 命令行执行入口（复用原有逻辑，无修改） ==========
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="【全自动建表+数据填充】从Excel提取结构新建表，CSV列名严格校验后分批插入")

    # 必选参数（核心：数据库AK、Excel表结构路径、CSV数据路径、表名）
    parser.add_argument("-k", "--db-ak", type=str, required=True, help="数据库AccessKey（必选，如：484rc）")
    parser.add_argument("-e", "--excel", type=str, required=True, help="表结构Excel文件完整路径（必选）")
    parser.add_argument("-c", "--csv", type=str, required=True, help="待插入数据CSV文件完整路径（必选）")
    parser.add_argument("-t", "--table-name", type=str, required=True, help="新建表的名称（必选，如：酶动力学参数表）")

    # 可选参数
    parser.add_argument("-s", "--sheet", type=str, default=None, help="Excel读取的Sheet名称/索引（默认第一个，如：Sheet1/3）")
    parser.add_argument("-hr", "--header-rows", type=int, default=1, help="新建表表头行数（默认1）")
    parser.add_argument("-bs", "--batch-size", type=int, default=5000, help="分批插入条数（默认5000，建议≤5000）")
    parser.add_argument("-j", "--json-save", type=str, default=None, help="CSV转JSON的保存路径（可选，如：./data.json）")
    parser.add_argument("-dr", "--desc-rows", type=int, default=0, help="表描述信息行数（默认0）")
    parser.add_argument("-di", "--desc-info", type=str, default=None, help="表描述信息（JSON格式，如：[[1,3]]）")

    # 解析参数
    args = parser.parse_args()
    sheet_to_read = 0 if args.sheet is None else args.sheet
    desc_info = json.loads(args.desc_info) if args.desc_info else None

    # 执行全流程
    auto_create_table_and_insert(
        db_ak=args.db_ak,
        excel_path=args.excel,
        csv_path=args.csv,
        table_name=args.table_name,
        sheet_name=sheet_to_read,
        header_rows=args.header_rows,
        batch_size=args.batch_size,
        json_save_path=args.json_save,
        desc_rows=args.desc_rows,
        desc_info=desc_info
    )