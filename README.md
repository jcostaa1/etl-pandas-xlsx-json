# ETL with pandas: xlsx with a JSON column → Parquet

A Python pipeline that reads a messy `.xlsx` spreadsheet, cleans it and converts the data types, splits a JSON column into separate columns, and saves the result as Parquet.

## Context

This project started as a **technical case test** I took when applying for a Data Engineer position in 2023. The challenge was to build an ETL in Python (with pandas) from an xlsx spreadsheet: fix the column data types (numbers, dates, text) and split a JSON column into separate columns.

After the process, I decided to **redo the exercise from scratch** and turn it into a portfolio project: I rebuilt the spreadsheet with fictional data, fixed the weak points of my first version (such as boolean conversion, date handling, and encoding), and organized the code into separate stages (Extract, Transform, Load), with logging and Parquet output.

No data, assignment text, or files from the original company were used here.

## The problem

The input spreadsheet had:

- **Broken encoding**: text such as `m√£e` and `Patr√≠cia` (UTF-8 read as Mac Roman).
- **Wrong types**: everything stored as text, including dates (`dd/mm/yyyy`), numbers, CPF (Brazilian tax ID), and phone numbers.
- **Formatted CPF and phone numbers**: `123.456.789-00` and `(11) 99999-9999`.
- **A `metadados` column with malformed JSON**, with missing quotes around the keys:
  `{questionario_enviado": "true", timestamp_envio": "2024-08-21 10:15:30"}`

## What the pipeline does

| Stage | What happens |
|---|---|
| **Extract** | Reads the xlsx with `dtype=str`, so pandas doesn't guess types (and doesn't drop the leading zeros of the CPF). |
| **Transform** | Fixes the encoding, renames columns to `snake_case`, converts numbers and dates, keeps only the digits in CPF and phone, and expands the JSON into columns. |
| **Load** | Saves to Parquet, which is columnar, compressed, and preserves data types. |

### Technical decisions

- `pd.to_numeric(errors="coerce")` and `pd.to_datetime(errors="coerce")`: invalid values become null instead of breaking the script, and the null count is logged at the end.
- Dates use an explicit `format="%d/%m/%Y"` to avoid confusion between day and month.
- `parse_meta` tries three ways to read the JSON: `json.loads`, `ast.literal_eval` (single quotes), and, as a last resort, a regex that fixes the quotes around the keys.
- `pd.json_normalize` turns the dictionaries into columns and also handles missing keys (they become `NaN`).
- CPF uses `zfill(11)` to restore leading zeros.

## Structure

```
.
├── database.xlsx     # fictional input data
├── etl_pipeline.py      # pipeline script
└── README.md
```

## Result

| Column | Final type |
|---|---|
| `nome`, `nome_mae` | string |
| `score` | integer |
| `peso` | decimal |
| `data_nascimento`, `data_nascimento_mae` | datetime |
| `telefone`, `cpf` | string (digits only) |
| `questionario_enviado` | boolean |
| `timestamp_envio` | datetime |

## Known limitations

- The regex that fixes the JSON may fail if a **value** contains the pattern `, word:` inside the text.
- The encoding fix assumes the case of UTF-8 read as Mac Roman; other cases would require a different conversion.
- CPF and phone numbers are personal data. With real data, the ideal approach would be to mask or hash them before saving (LGPD, Brazil's data protection law).
