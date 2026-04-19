# Bohr Database SDK — 数据库维护工具

管理 Bohrium 平台上四个数据库的建表、批量上传与表结构变更。

> **使用前必读：** 所有脚本通过环境变量 `BOHR_ACCESS_KEY` 读取主账号密钥，请先执行：
> ```bash
> export BOHR_ACCESS_KEY=<your_main_access_key>
> ```

---

## 目录结构

```
bohr_database_sdk/
├── upload_database_tables_omit_empty.py   # 核心：建表 + 批量上传
├── bio_only.json                          # 生物反应库批量配置（10张表）
├── enzy_only.json                         # 酶库批量配置（3张表）
├── metabolite_only.json                   # 代谢物库批量配置（1张表）
├── nano_only.json                         # 纳米酶库批量配置（8张表）
├── run_upload.sh                          # 一键分库上传（支持指定单个库）
├── run_upload_single.sh                   # 单张表上传示例
├── verify_setup.sh                        # 上传前环境预检
├── maintaining_field_descriptions/
│   ├── script.py                          # 修改已有表的表结构（AlterTable）
│   ├── bio/      （10个CSV）              # 生物反应库字段描述
│   ├── enzy/     （3个CSV）               # 酶库字段描述
│   ├── metabolite/（1个CSV）              # 代谢物库字段描述
│   └── nano/     （8个CSV）               # 纳米酶库字段描述
└── new_table/
    └── script.py                          # 从Excel/CSV建新表并灌数
```

---

## 依赖安装

```bash
pip3 install bohrium_open_sdk pandas openpyxl
```

---

## 数据库与 AccessKey 一览

| 数据库 | AK | 表数 |
|--------|----|------|
| 纳米酶库 | `878qb` | 8 |
| 代谢物库 | `351de` | 1 |
| 酶库 | `555fu` | 3 |
| 生物反应库 | `531km` | 10 |

---

## 工作流一：批量上传（最常用）

### 核心脚本

`upload_database_tables_omit_empty.py` — 读取字段描述 CSV → 建表 → 批量插入数据。

**空列处理**：CSV 某列为空时，该字段不写入 JSON（不传键），前端显示 null，避免被误显示为 0。  
**inf 处理**：加 `--inf-replace` 后，仅对数值列（`dataType=num`）将 `inf/-inf` 替换为 `±1e30`，避免非标准 JSON 导致接口报错（bio 库表9需要）。

### 命令参数

```
-k / --db-ak        数据库 AccessKey（必填）
-b / --batch-config 批量配置 JSON 路径（批量模式必填）
-d / --desc         字段描述 CSV 路径（单表模式必填）
-c / --csv          数据 CSV 路径（单表模式必填）
-t / --table-name   表名称（单表模式必填）
-bs/ --batch-size   每批插入条数（默认 5000）
--skip-exists       表已存在时跳过（不报错）
--inf-replace       数值列 inf → ±1e30（bio 库必须加）
```

### 各库上传命令

**纳米酶库（878qb，8张表）**
```bash
python3 /share/allpdfs/bohr_database_sdk/upload_database_tables_omit_empty.py \
  -k "878qb" -b /share/allpdfs/bohr_database_sdk/nano_only.json \
  --batch-size 5000 --skip-exists
```

**代谢物库（351de，1张表）**
```bash
python3 /share/allpdfs/bohr_database_sdk/upload_database_tables_omit_empty.py \
  -k "351de" -b /share/allpdfs/bohr_database_sdk/metabolite_only.json \
  --batch-size 2000 --skip-exists
```

**酶库（555fu，3张表）**
```bash
python3 /share/allpdfs/bohr_database_sdk/upload_database_tables_omit_empty.py \
  -k "555fu" -b /share/allpdfs/bohr_database_sdk/enzy_only.json \
  --batch-size 5000 --skip-exists
```

**生物反应库（531km，10张表）**
```bash
# 必须加 --inf-replace（表9含 inf 值）
python3 /share/allpdfs/bohr_database_sdk/upload_database_tables_omit_empty.py \
  -k "531km" -b /share/allpdfs/bohr_database_sdk/bio_only.json \
  --batch-size 5000 --skip-exists --inf-replace
```

大表可在命令前加 `CLIENT_TIMEOUT=300` 延长超时。

### 一键运行所有库

```bash
export BOHR_ACCESS_KEY=<your_key>
bash /share/allpdfs/bohr_database_sdk/run_upload.sh          # 全部4个库
bash /share/allpdfs/bohr_database_sdk/run_upload.sh nano     # 只跑纳米酶库
bash /share/allpdfs/bohr_database_sdk/run_upload.sh bio      # 只跑生物反应库
```

### 批量配置 JSON 格式

每个 `*_only.json` 格式如下，`tables` 数组按顺序上传：

```json
{
  "tables": [
    {
      "table_name": "1_reactions_core",
      "desc_file": "/share/allpdfs/bohr_database_sdk/maintaining_field_descriptions/bio/1_reactions_core.csv",
      "data_file": "/share/allpdfs/final_bioreaction_extraction_database/3.bioreaction_database/1_reactions_core.csv"
    }
  ]
}
```

### 字段描述 CSV 格式

`maintaining_field_descriptions/` 下各 CSV 定义表结构，每行一个字段：

```csv
字段名,数据类型,含义
reaction_id,str,反应唯一标识符
temperature,num,反应温度（K）
smiles,smiles,底物SMILES结构式
```

`数据类型` 可选值：`str`、`num`、`smiles`。

---

## 工作流二：修改已有表的表结构

**适用场景**：表已建好并有数据，需要新增/修改字段描述（不删数据）。

**脚本**：`maintaining_field_descriptions/script.py`

```bash
# 从 CSV 更新表结构
python3 /share/allpdfs/bohr_database_sdk/maintaining_field_descriptions/script.py \
  -c /share/allpdfs/bohr_database_sdk/maintaining_field_descriptions/bio/2_enzymes.csv \
  -ak <target_table_ak>

# 从 Excel 更新表结构
python3 /share/allpdfs/bohr_database_sdk/maintaining_field_descriptions/script.py \
  -f /path/to/schema.xlsx \
  -s "Sheet1" \
  -ak <target_table_ak>
```

| 参数 | 说明 |
|------|------|
| `-c` | 字段描述 CSV 路径（与 `maintaining_field_descriptions/` 下格式相同） |
| `-f` | Excel 路径（含字段名/数据类型/描述列） |
| `-s` | Excel sheet 名称（默认第一个） |
| `-ak`| 目标表的 AccessKey（必填） |

> 此脚本调用 `AlterTable` 接口，仅更新 schema，不影响已有数据。

---

## 工作流三：建新表（从 Excel 定义表结构）

**适用场景**：有新的数据库表需要从 Excel 定义字段并首次灌入数据。

**脚本**：`new_table/script.py`

```bash
python3 /share/allpdfs/bohr_database_sdk/new_table/script.py \
  -k <db_ak> \
  -e /path/to/schema.xlsx \
  -c /path/to/data.csv \
  -t <table_name>
```

| 参数 | 说明 |
|------|------|
| `-k` | 数据库 AccessKey |
| `-e` | Excel schema 文件路径 |
| `-c` | 数据 CSV 路径 |
| `-t` | 表名称 |

> 与工作流一的区别：schema 来源是 Excel 而非 CSV，适合首次定义新表时使用。

---

## 辅助脚本

### verify_setup.sh — 上传前预检

检查脚本、JSON 配置、字段描述 CSV、数据目录、Python 依赖是否全部就绪：

```bash
bash /share/allpdfs/bohr_database_sdk/verify_setup.sh
```

### run_upload_single.sh — 单表上传示例

已内置代谢物库单表配置，可参考修改路径和表名后使用：

```bash
bash /share/allpdfs/bohr_database_sdk/run_upload_single.sh
```

---

## 历史改动记录

### 纳米酶库表 6 表名缩短

表名 `6_nanozyme_characterization_size`（33字符）超过平台约 25～30 字符限制，建表报 INVALID_PARAM。

| 项目 | 修改前 | 修改后 |
|------|--------|--------|
| 表名 | `6_nanozyme_characterization_size` | `6_nanozyme_char_size` |
| 描述文件 | `nano/6_nanozyme_characterization_size_standardized_description.csv` | `nano/6_nanozyme_char_size_standardized_description.csv` |
| 数据文件 | `4.nanozyme_database/6_nanozyme_characterization_size_standardized.csv` | `4.nanozyme_database/6_nanozyme_char_size_standardized.csv` |

描述文件、数据文件通过重命名完成，内容未改；`nano_only.json` 中仅更新表6一条配置。

### 生物反应库表 2 描述文件补列

数据文件 `2_enzymes.csv` 比原描述文件多 4 列（`sequence`、`match_source`、`match_description`、`seq_confidence`），且第 23 行含义列含英文逗号导致 CSV 解析报错。

修改 `maintaining_field_descriptions/bio/2_enzymes.csv`：字段顺序与数据文件对齐，补充 4 个新字段行，含逗号的含义用双引号包裹。

### 生物反应库表 9 的 inf 问题

`9_inhibition_params.csv` 的 `value` 列有 3 行值为 `inf`，pandas 读取后转为 `float('inf')`，`json.dumps` 输出 `Infinity`（非标准JSON），接口报 `invalid character 'I'`。

解决：上传 bio 库时加 `--inf-replace`，脚本对 `dataType=num` 的列将 inf/-inf 替换为 ±1e30 后序列化。
