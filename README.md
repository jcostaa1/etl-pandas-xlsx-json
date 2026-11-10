# ETL com pandas: xlsx com coluna JSON → Parquet

Pipeline em Python que lê uma planilha `.xlsx` com dados bagunçados, limpa e converte os tipos, separa uma coluna em JSON em colunas próprias e salva o resultado em Parquet.

> Os dados do projeto são **fictícios**, criados só para demonstração.

## Contexto

Este projeto nasceu de um **teste de caso técnico** que fiz ao me candidatar a uma vaga de Engenheira de Dados em 2023. O desafio era montar um ETL em Python (com pandas) a partir de uma planilha xlsx: ajustar a tipagem das colunas (números, datas, textos) e separar uma coluna em JSON em colunas próprias.

Depois do processo, decidi **refazer o exercício do zero** e transformá-lo em um projeto de portfólio: reconstruí a planilha com dados fictícios, corrigi os pontos fracos da minha primeira versão (como a conversão de booleanos, o tratamento de datas e o encoding) e organizei o código em etapas separadas (Extract, Transform, Load), com logging e saída em Parquet.

Nenhum dado, enunciado ou arquivo da empresa original foi usado aqui.

## O problema

A planilha de entrada tinha:

- **Encoding quebrado**: textos como `m√£e` e `Patr√≠cia` (UTF-8 lido como Mac Roman).
- **Tipos errados**: tudo como texto, incluindo datas (`dd/mm/aaaa`), números, CPF e telefone.
- **CPF e telefone formatados**: `123.456.789-00` e `(11) 99999-9999`.
- **Coluna `metadados` em JSON malformado**, com aspas faltando nas chaves:
  `{questionario_enviado": "true", timestamp_envio": "2024-08-21 10:15:30"}`

## O que o pipeline faz

| Etapa | O que acontece |
|---|---|
| **Extract** | Lê o xlsx com `dtype=str`, para o pandas não adivinhar tipos (e não perder zeros do CPF). |
| **Transform** | Conserta o encoding, renomeia colunas para `snake_case`, converte números e datas, deixa CPF e telefone só com dígitos e expande o JSON em colunas. |
| **Load** | Salva em Parquet, que é colunar, comprimido e preserva os tipos. |

### Decisões técnicas

- `pd.to_numeric(errors="coerce")` e `pd.to_datetime(errors="coerce")`: valores inválidos viram nulo em vez de quebrar o script, e a contagem de nulos é logada no final.
- Datas com `format="%d/%m/%Y"` explícito, para evitar confusão entre dia e mês.
- `parse_meta` tenta três formas de ler o JSON: `json.loads`, `ast.literal_eval` (aspas simples) e, por último, uma regex que conserta as aspas das chaves.
- `pd.json_normalize` transforma os dicionários em colunas e também acha chaves ausentes (viram `NaN`).
- CPF com `zfill(11)` para recuperar zeros à esquerda.

## Estrutura

```
.
├── dados_teste.xlsx     # dados fictícios de entrada
├── etl_pipeline.py      # pipeline em script
└── README.md
```

## Resultado

| Coluna | Tipo final |
|---|---|
| `nome`, `nome_mae` | string |
| `score` | inteiro |
| `peso` | decimal |
| `data_nascimento`, `data_nascimento_mae` | datetime |
| `telefone`, `cpf` | string (só dígitos) |
| `questionario_enviado` | booleano |
| `timestamp_envio` | datetime |

## Limitações conhecidas

- A regex que conserta o JSON pode errar se um **valor** tiver o padrão `, palavra:` dentro do texto.
- O conserto de encoding assume o caso UTF-8 lido como Mac Roman; outros casos exigiriam outra conversão.
- CPF e telefone são dados pessoais. Em dados reais, o ideal seria mascarar ou aplicar hash antes de salvar (LGPD).
