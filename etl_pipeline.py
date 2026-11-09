import json
import ast
import logging
import re
import sys

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

COLUNAS = {
    "data de nascimento": "data_nascimento",
    "nome da mãe": "nome_mae",
    "data de nascimento da mãe": "data_nascimento_mae",
}


def fix_mojibake(s):
    if not isinstance(s, str):
        return s
    try:
        return s.encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def parse_meta(x):
    if pd.isna(x):
        return {}
    x = str(x).strip()
    try:
        return json.loads(x)
    except json.JSONDecodeError:
        pass
    try:
        return ast.literal_eval(x)
    except (ValueError, SyntaxError):
        pass

    x = re.sub(r'([{,]\s*)"?(\w+)"?(\s*:)', r'\1"\2"\3', x)
    return json.loads(x)


def extract(path):
    logging.info("Lendo %s", path)
    return pd.read_excel(path, dtype=str)


def transform(df):
    df.columns = [fix_mojibake(c) for c in df.columns]
    df = df.rename(columns=COLUNAS)

    for c in ["nome", "nome_mae"]:
        df[c] = df[c].map(fix_mojibake).astype("string").str.strip()

    for c in ["score", "peso"]:
        df[c] = pd.to_numeric(df[c].str.replace(",", ".", regex=False), errors="coerce")

    for c in ["data_nascimento", "data_nascimento_mae"]:
        df[c] = pd.to_datetime(df[c], format="%d/%m/%Y", errors="coerce")

    df["telefone"] = df["telefone"].str.replace(r"\D", "", regex=True)
    df["cpf"] = df["cpf"].str.replace(r"\D", "", regex=True).str.zfill(11)

    meta = pd.json_normalize(df["metadados"].apply(parse_meta))
    meta["questionario_enviado"] = (
        meta["questionario_enviado"].astype(str).str.lower()
        .map({"true": True, "false": False}).astype("boolean")
    )
    meta["timestamp_envio"] = pd.to_datetime(meta["timestamp_envio"], errors="coerce")

    df = pd.concat([df.drop(columns="metadados").reset_index(drop=True), meta], axis=1)

    logging.info("Nulos por coluna após conversão:\n%s", df.isna().sum().to_string())
    return df


def load(df, path="dados_transformados.parquet"):
    df.to_parquet(path, index=False)
    logging.info("Salvo em %s (%d linhas)", path, len(df))


if __name__ == "__main__":
    entrada = sys.argv[1] if len(sys.argv) > 1 else "dados_teste.xlsx"
    load(transform(extract(entrada)))
