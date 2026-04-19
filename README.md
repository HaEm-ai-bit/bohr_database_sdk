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
├── scripts/
│   ├── upload.py          # 核心：建表 + 批量上传
│   ├── alter_schema.py    # 修改已有表的表结构（AlterTable）
│   └── create_table.py    # 从 Excel/CSV 建新表并灌数
├── configs/
│   ├── bio.json           # 生物反应库批量配置（10 张表）
│   ├── enzy.json          # 酶库批量配置（3 张表）
│   ├── metabolite.json    # 代谢物库批量配置（1 张表）
│   └── nano.json          # 纳米酶库批量配置（8 张表）
├── schemas/
│   ├── bio/               # 生物反应库字段描述（10 个 CSV）
│   ├── enzy/              # 酶库字段描述（3 个 CSV）
│   ├── metabolite/        # 代谢物库字段描述（1 个 CSV）
│   └── nano/              # 纳米酶库字段描述（8 个 CSV）
├── bin/
│   ├── run.sh             # 一键分库上传
│   ├── run_single.sh      # 单张表上传示例
│   └── check.sh           # 上传前环境预检
└── README.md
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

`scripts/upload.py` — 读取字段描述 CSV → 建表 → 批量插入数据。

**空列处理**：CSV 某列为空时，该字段不写入 JSON（不传键），前端显示 null。  
**inf 处理**：加 `--inf-replace` 后，仅对数值列将 `inf/-inf` 替换为 `±1e30`（bio 库表9需要）。

### 命令参数

```
-k / --db-ak        数据库 AccessKey（必填）
-b / --batch-config 批量配置 JSON 路径（批量模式必填）
-d / --desc         字段描述 CSV 路径（单表模式必填）
-c / --csv          数据 CSV 路径（单表模式必填）
-t / --table-name   表名称（单表模式必填）
-bs/ --batch-size   每批插入条数（默认 5000）
--skip-exists       表已存在时跳过
--inf-replace       数值列 inf → ±1e30（bio 库必须加）
```

### 各库上传命令

```bash
# 纳米酶库（878qb，8张表）
python3 scripts/upload.py -k "878qb" -b configs/nano.json --batch-size 5000 --skip-exists

# 代谢物库（351de，1张表）
python3 scripts/upload.py -k "351de" -b configs/metabolite.json --batch-size 2000 --skip-exists

# 酶库（555fu，3张表）
python3 scripts/upload.py -k "555fu" -b configs/enzy.json --batch-size 5000 --skip-exists

# 生物反应库（531km，10张表）—— 必须加 --inf-replace
python3 scripts/upload.py -k "531km" -b configs/bio.json --batch-size 5000 --skip-exists --inf-replace
```

大表可在命令前加 `CLIENT_TIMEOUT=300` 延长超时。

### 一键运行

```bash
export BOHR_ACCESS_KEY=<your_key>

bash bin/run.sh          # 全部 4 个库
bash bin/run.sh nano     # 只跑纳米酶库
bash bin/run.sh bio      # 只跑生物反应库
bash bin/run.sh enzy     # 只跑酶库
bash bin/run.sh metabolite # 只跑代谢物库
```

### 配置文件格式（`configs/*.json`）

```json
{
  "tables": [
    {
      "table_name": "1_reactions_core",
      "desc_file": "/share/allpdfs/bohr_database_sdk/schemas/bio/1_reactions_core.csv",
      "data_file": "/share/allpdfs/final_bioreaction_extraction_database/3.bioreaction_database/1_reactions_core.csv"
    }
  ]
}
```

### 字段描述 CSV 格式（`schemas/**/*.csv`）

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

```bash
# 从 CSV 更新表结构
python3 scripts/alter_schema.py \
  -c schemas/bio/2_enzymes.csv \
  -ak <target_table_ak>

# 从 Excel 更新表结构
python3 scripts/alter_schema.py \
  -f /path/to/schema.xlsx \
  -s "Sheet1" \
  -ak <target_table_ak>
```

| 参数 | 说明 |
|------|------|
| `-c` | 字段描述 CSV 路径 |
| `-f` | Excel 路径 |
| `-s` | Excel sheet 名称（默认第一个） |
| `-ak`| 目标表的 AccessKey（必填） |

---

## 工作流三：建新表（从 Excel 定义表结构）

**适用场景**：有新的数据表需要从 Excel 定义字段并首次灌入数据。

```bash
python3 scripts/create_table.py \
  -k <db_ak> \
  -e /path/to/schema.xlsx \
  -c /path/to/data.csv \
  -t <table_name>
```

---

## 辅助脚本

```bash
bash bin/check.sh        # 上传前预检（验证脚本/配置/依赖是否就绪）
bash bin/run_single.sh   # 单张表上传示例（修改脚本内变量后使用）
```

---

## 历史改动记录

### 纳米酶库表 6 表名缩短

表名 `6_nanozyme_characterization_size`（33字符）超过平台约 25～30 字符限制，建表报 INVALID_PARAM。

| 项目 | 修改前 | 修改后 |
|------|--------|--------|
| 表名 | `6_nanozyme_characterization_size` | `6_nanozyme_char_size` |
| 描述文件 | `schemas/nano/6_nanozyme_characterization_size_standardized_description.csv` | `schemas/nano/6_nanozyme_char_size_standardized_description.csv` |
| 数据文件 | `4.nanozyme_database/6_nanozyme_characterization_size_standardized.csv` | `4.nanozyme_database/6_nanozyme_char_size_standardized.csv` |

### 生物反应库表 2 描述文件补列

数据文件 `2_enzymes.csv` 比原描述文件多 4 列（`sequence`、`match_source`、`match_description`、`seq_confidence`），且第 23 行含义列含英文逗号导致 CSV 解析报错。修改 `schemas/bio/2_enzymes.csv`：字段顺序对齐，补充 4 个新字段行，含逗号的含义用双引号包裹。

### 生物反应库表 9 的 inf 问题

`9_inhibition_params.csv` 的 `value` 列有 3 行值为 `inf`，pandas 读取后转为 `float('inf')`，`json.dumps` 输出 `Infinity`（非标准JSON），接口报 `invalid character 'I'`。解决：上传 bio 库时加 `--inf-replace`，脚本对数值列将 inf/-inf 替换为 ±1e30。
