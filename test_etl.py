from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from etl_pipeline import extract, fix_mojibake, load, parse_meta, transform

XLSX = Path(__file__).resolve().parent.parent / "dados_teste.xlsx"

META_MALFORMADO = '{questionario_enviado": "true", timestamp_envio": "2024-08-21 10:15:30"}'

@pytest.mark.parametrize(
    "quebrado, esperado",
    [
        ("m√£e", "mãe"),
        ("Patr√≠cia", "Patrícia"),
        ("Jo√£o Almeida", "João Almeida"),
        ("S√¥nia Oliveira", "Sônia Oliveira"),
        ("nome da m√£e", "nome da mãe"),
    ],
)
def test_fix_mojibake_corrige_texto_quebrado(quebrado, esperado):
    assert fix_mojibake(quebrado) == esperado


@pytest.mark.parametrize("texto", ["Ana Souza", "João", "Patrícia Martins", "", "mãe"])
def test_fix_mojibake_nao_altera_texto_correto(texto):
    assert fix_mojibake(texto) == texto


@pytest.mark.parametrize("valor", [None, 42, 3.14, np.nan])
def test_fix_mojibake_ignora_valores_que_nao_sao_texto(valor):
    resultado = fix_mojibake(valor)
    if isinstance(valor, float) and np.isnan(valor):
        assert np.isnan(resultado)
    else:
        assert resultado == valor


def test_parse_meta_json_valido():
    texto = '{"questionario_enviado": "true", "timestamp_envio": "2024-08-21 10:15:30"}'
    assert parse_meta(texto) == {
        "questionario_enviado": "true",
        "timestamp_envio": "2024-08-21 10:15:30",
    }


def test_parse_meta_aspas_simples():
    assert parse_meta("{'questionario_enviado': 'false'}") == {"questionario_enviado": "false"}


def test_parse_meta_json_malformado_do_arquivo():
    assert parse_meta(META_MALFORMADO) == {
        "questionario_enviado": "true",
        "timestamp_envio": "2024-08-21 10:15:30",
    }


def test_parse_meta_chaves_sem_nenhuma_aspa():
    texto = '{questionario_enviado: "true", timestamp_envio: "2024-08-21 10:15:30"}'
    assert parse_meta(texto) == {
        "questionario_enviado": "true",
        "timestamp_envio": "2024-08-21 10:15:30",
    }


def test_parse_meta_nao_quebra_o_horario_do_timestamp():
    """O regex que conserta as chaves não pode mexer nos ':' do horário."""
    resultado = parse_meta(META_MALFORMADO)
    assert resultado["timestamp_envio"] == "2024-08-21 10:15:30"


def test_parse_meta_ignora_espacos_nas_pontas():
    assert parse_meta('   {"a": "1"}  ') == {"a": "1"}


@pytest.mark.parametrize("nulo", [pd.NA, np.nan, None])
def test_parse_meta_nulo_devolve_dicionario_vazio(nulo):
    assert parse_meta(nulo) == {}


def test_parse_meta_texto_irrecuperavel_levanta_erro():
    with pytest.raises(ValueError):  
        parse_meta("isso não é um json")


@pytest.fixture
def df_bruto():
    """Três linhas com os defeitos do arquivo original, cabeçalho com encoding quebrado."""
    return pd.DataFrame(
        {
            "nome": ["Ana Souza", "Jo√£o Almeida", "Maria Teste"],
            "score": ["85", "abc", "70"],
            "peso": ["55,5", "80.4", "62"],
            "data de nascimento": ["15/08/1998", "03/04/2000", "32/13/2000"],
            "nome da m√£e": ["Maria Souza", "Ana Almeida", "Joana Teste"],
            "data de nascimento da m√£e": ["22/03/1975", "10/10/1960", "01/01/1970"],
            "telefone": ["(11) 99999-9999", "(21) 90000-0000", "11 98888-7777"],
            "cpf": ["012.345.678-99", "123.456.789-00", "123456789"],
            "metadados": [
                META_MALFORMADO,
                '{"questionario_enviado": "false", "timestamp_envio": "2024-08-22 06:26:00"}',
                np.nan,
            ],
        }
    )


@pytest.fixture
def df_limpo(df_bruto):
    return transform(df_bruto)


def test_transform_renomeia_colunas_e_remove_metadados(df_limpo):
    assert list(df_limpo.columns) == [
        "nome", "score", "peso", "data_nascimento", "nome_mae", "data_nascimento_mae",
        "telefone", "cpf", "questionario_enviado", "timestamp_envio",
    ]


def test_transform_preserva_numero_de_linhas(df_bruto, df_limpo):
    assert len(df_limpo) == 3


def test_transform_corrige_encoding_dos_textos(df_limpo):
    assert df_limpo["nome"].tolist() == ["Ana Souza", "João Almeida", "Maria Teste"]


def test_transform_converte_numericos(df_limpo):
    assert pd.api.types.is_numeric_dtype(df_limpo["score"])
    assert pd.api.types.is_numeric_dtype(df_limpo["peso"])


def test_transform_peso_com_virgula_vira_decimal(df_limpo):
    assert df_limpo["peso"].iloc[0] == 55.5


def test_transform_numero_invalido_vira_nulo_sem_quebrar(df_limpo):
    assert pd.isna(df_limpo["score"].iloc[1])
    assert df_limpo["score"].iloc[0] == 85


def test_transform_datas_sao_lidas_como_dia_mes_ano(df_limpo):
    # 03/04/2000 é 3 de abril (e não 4 de março)
    assert df_limpo["data_nascimento"].iloc[1] == pd.Timestamp(2000, 4, 3)
    assert df_limpo["data_nascimento_mae"].iloc[0] == pd.Timestamp(1975, 3, 22)
    assert pd.api.types.is_datetime64_any_dtype(df_limpo["data_nascimento"])


def test_transform_data_invalida_vira_nat(df_limpo):
    assert pd.isna(df_limpo["data_nascimento"].iloc[2])


def test_transform_cpf_so_digitos_e_zero_a_esquerda(df_limpo):
    assert df_limpo["cpf"].iloc[0] == "01234567899"
    assert df_limpo["cpf"].iloc[1] == "12345678900"


def test_transform_cpf_que_perdeu_zeros_volta_com_11_digitos(df_limpo):
    assert df_limpo["cpf"].iloc[2] == "00123456789"
    assert (df_limpo["cpf"].str.len() == 11).all()


def test_transform_telefone_so_digitos(df_limpo):
    assert df_limpo["telefone"].tolist() == ["11999999999", "21900000000", "11988887777"]


def test_transform_json_vira_colunas_tipadas(df_limpo):
    assert str(df_limpo["questionario_enviado"].dtype) == "boolean"
    assert pd.api.types.is_datetime64_any_dtype(df_limpo["timestamp_envio"])
    assert df_limpo["questionario_enviado"].iloc[0] == True
    assert df_limpo["questionario_enviado"].iloc[1] == False
    assert df_limpo["timestamp_envio"].iloc[0] == pd.Timestamp("2024-08-21 10:15:30")


def test_transform_linha_sem_metadados_fica_com_nulos(df_limpo):
    assert pd.isna(df_limpo["questionario_enviado"].iloc[2])
    assert pd.isna(df_limpo["timestamp_envio"].iloc[2])


def test_transform_booleano_nao_cai_na_armadilha_do_astype_bool():
    """Com astype(bool), o texto 'false' viraria True. Aqui precisa virar False."""
    df = pd.DataFrame(
        {
            "nome": ["A"], "score": ["1"], "peso": ["1"], "data de nascimento": ["01/01/2000"],
            "nome da mãe": ["B"], "data de nascimento da mãe": ["01/01/1970"],
            "telefone": ["1"], "cpf": ["1"],
            "metadados": ['{"questionario_enviado": "False", "timestamp_envio": "2024-01-01 00:00:00"}'],
        }
    )
    resultado = transform(df)
    assert resultado["questionario_enviado"].iloc[0] == False


@pytest.mark.skipif(not XLSX.exists(), reason="dados_teste.xlsx não encontrado na raiz do projeto")
class TestComArquivoDeExemplo:
    def test_extract_le_tudo_como_texto(self):
        df = extract(XLSX)
        assert len(df) == 19

        assert "." in df["cpf"].iloc[0]

    def test_pipeline_completo_sem_nulos(self):
        df = transform(extract(XLSX))
        assert len(df) == 19
        assert df.isna().sum().sum() == 0

    def test_pipeline_completo_sem_encoding_quebrado(self):
        df = transform(extract(XLSX))
        textos = pd.concat([df["nome"], df["nome_mae"]])
        assert not textos.str.contains("√").any()

    def test_pipeline_completo_cpf_e_telefone(self):
        df = transform(extract(XLSX))
        assert df["cpf"].str.fullmatch(r"\d{11}").all()
        assert df["telefone"].str.fullmatch(r"\d{10,11}").all()


def test_load_grava_parquet_e_preserva_tipos(tmp_path):
    pytest.importorskip("pyarrow")
    df = pd.DataFrame(
        {
            "cpf": ["01234567899"],
            "data": pd.to_datetime(["2000-04-03"]),
            "ok": pd.array([True], dtype="boolean"),
        }
    )
    destino = tmp_path / "saida.parquet"
    load(df, str(destino))
    lido = pd.read_parquet(destino)
    assert lido["cpf"].iloc[0] == "01234567899"
    assert pd.api.types.is_datetime64_any_dtype(lido["data"])
    assert len(lido) == 1
