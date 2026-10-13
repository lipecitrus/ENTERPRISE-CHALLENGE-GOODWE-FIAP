"""IA para anomalias e previsão de uso do EV ChargeOps.

Lê os CSVs reais/sintéticos pela interface já existente em leitor_uso.py.
Gera fatura_saida/relatorio_ia.csv e imprime um resumo. Não altera faturas.

Dependências: pandas (já usado pelo projeto) e scikit-learn.
Uso: python ia_uso.py [pasta_uso] [pasta_saida] [dias_previsao]
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestRegressor

from leitor_uso import ErroLeitura, UsoSource
from src.rateio import carregar_parametros

RAIZ = Path(__file__).resolve().parent
PASTA_USO_PADRAO = RAIZ / "uso_carregador"
PASTA_SAIDA_PADRAO = RAIZ / "fatura_saida"
ANTECEDENCIA_MIN = carregar_parametros().antecedencia      # a mesma regra do rateio (config/parametros_rateio.csv)


def _features_sessao(sessao) -> dict:
    duracao_h = max(sessao.duracao_min / 60.0, 1 / 60)
    potencias = [l.potencia_kw for l in sessao.leituras if l.potencia_kw is not None and l.potencia_kw >= 0]
    leituras_soc = [(l.t, l.soc_pct, l.energia_kwh) for l in sessao.leituras if l.soc_pct is not None]
    socs = [float(x[1]) for x in leituras_soc]

    soc_regride_com_energia = any(
        b[1] < a[1] - 2.0 and b[2] > a[2] + 0.05
        for a, b in zip(leituras_soc, leituras_soc[1:])
    )
    reserva = sessao.reserva
    return {
        "sessao_id": sessao.id,
        "usuario_id": sessao.usuario_id or "NAO_IDENTIFICADO",
        "inicio": sessao.inicio,
        "kwh": float(sessao.kwh),
        "duracao_min": max(sessao.duracao_min, 0),
        "potencia_media_kw": float(sessao.kwh) / duracao_h,
        "potencia_max_kw": max(potencias) if potencias else 0.0,
        "hora_inicio": sessao.inicio.hour,
        "dia_semana": sessao.inicio.weekday(),
        "identificada": sessao.identificada,
        "status": sessao.status,
        "identificacao": (sessao.identificacao or "").strip().lower(),
        "agendamento_id": reserva.id if reserva else "",
        "reserva_inicio": reserva.inicio if reserva else None,
        "reserva_fim": reserva.fim if reserva else None,
        "reserva_criada_em": reserva.criada_em if reserva else None,
        "soc_min": min(socs) if socs else None,
        "soc_max": max(socs) if socs else None,
        "soc_inicio": socs[0] if socs else None,
        "soc_fim": socs[-1] if socs else None,
        "soc_regride_com_energia": soc_regride_com_energia,
    }


def detectar_anomalias(sessoes) -> pd.DataFrame:
    """Detecta regras operacionais explicáveis e padrões estatísticos incomuns.

    Regras de SOC e agendamento são determinísticas; IsolationForest é complementar.
    Sessões avulsas são sinalizadas para revisão, não declaradas automaticamente inválidas.
    """
    colunas = ["tipo", "sessao_id", "usuario_id", "inicio", "kwh", "duracao_min", "score_ia", "motivo"]
    if not sessoes:
        return pd.DataFrame(columns=colunas)

    dados = pd.DataFrame([_features_sessao(s) for s in sessoes])
    num = ["kwh", "duracao_min", "potencia_media_kw", "potencia_max_kw", "hora_inicio", "dia_semana"]
    dados[num] = dados[num].replace([float("inf"), float("-inf")], 0).fillna(0)
    dados["score_ia"] = 0.0
    dados["flag_ia"] = False
    if len(dados) >= 5:
        modelo = IsolationForest(n_estimators=150, contamination=0.05, random_state=42)
        dados["flag_ia"] = modelo.fit_predict(dados[num]) == -1
        dados["score_ia"] = -modelo.decision_function(dados[num])

    alertas = []
    for _, r in dados.iterrows():
        motivos = []
        tipos = []
        def sinalizar(tipo: str, motivo: str) -> None:
            tipos.append(tipo)
            motivos.append(motivo)

        if r["kwh"] < -0.01:
            sinalizar("medidor", "energia acumulada diminuiu entre início e fim")
        if r["duracao_min"] <= 0:
            sinalizar("duracao", "duração da sessão nula ou negativa")
        if r["kwh"] > 0 and r["duracao_min"] > 0 and r["potencia_media_kw"] > 100:
            sinalizar("potencia", "potência média acima de 100 kW; revisar medição/configuração")
        if not bool(r["identificada"]):
            sinalizar("identificacao", "sessão sem identificação completa")
        if pd.notna(r["soc_min"]) and (r["soc_min"] < 0 or r["soc_max"] > 100):
            sinalizar("soc_fora_intervalo", f"SOC fora do intervalo válido de 0% a 100% (mín. {r['soc_min']:.1f}%, máx. {r['soc_max']:.1f}%)")
        if bool(r["soc_regride_com_energia"]):
            sinalizar("soc_incoerente", "SOC caiu mais de 2 pontos percentuais enquanto o medidor acumulado aumentou; revisar telemetria")
        if pd.notna(r["soc_inicio"]) and pd.notna(r["soc_fim"]) and r["kwh"] > 0 and r["soc_fim"] + 2 < r["soc_inicio"]:
            sinalizar("soc_incoerente", "SOC final ficou mais de 2 p.p. abaixo do inicial apesar de consumo positivo")

        ag_id = str(r["agendamento_id"] or "").strip()
        res_ini, res_fim, res_criada = r["reserva_inicio"], r["reserva_fim"], r["reserva_criada_em"]
        if ag_id:                       # uso avulso é permitido (paga a taxa); só confere as reservas
            if pd.notna(res_ini) and r["inicio"] < res_ini:
                sinalizar("fora_agendamento", "sessão iniciada antes da janela da reserva")
            if pd.notna(res_fim) and r["inicio"] >= res_fim:
                sinalizar("fora_agendamento", "sessão iniciada no fim ou após o término da reserva")
            if pd.notna(res_ini) and pd.notna(res_criada) and (res_ini - res_criada) < ANTECEDENCIA_MIN:
                minutos = int(ANTECEDENCIA_MIN.total_seconds() // 60)
                sinalizar("antecedencia_reserva", f"reserva criada com menos de {minutos} minutos de antecedência")
            if r["identificacao"] != "reserva":
                sinalizar("agendamento_identificacao", "sessão possui agendamento associado, mas identificação não indica uso por reserva")

        if bool(r["flag_ia"]):
            sinalizar("estatistica", "combinação de consumo, duração e potência diferente do padrão observado")
        if motivos:
            alertas.append({
                "tipo": ";".join(dict.fromkeys(tipos)), "sessao_id": r["sessao_id"], "usuario_id": r["usuario_id"],
                "inicio": r["inicio"].strftime("%Y-%m-%d %H:%M:%S"), "kwh": round(float(r["kwh"]), 3),
                "duracao_min": int(r["duracao_min"]), "score_ia": round(float(r["score_ia"]), 5),
                "motivo": "; ".join(dict.fromkeys(motivos)),
            })
    return pd.DataFrame(alertas, columns=colunas)

def prever_uso_diario(sessoes, dias: int = 7) -> pd.DataFrame:
    """Prevê kWh/dia por Random Forest com calendário e defasagens; fallback para média."""
    colunas = ["tipo", "data", "kwh_previsto", "metodo", "observacao"]
    if dias < 1:
        raise ValueError("dias_previsao deve ser >= 1")
    if not sessoes:
        return pd.DataFrame([{
            "tipo": "previsao", "data": "", "kwh_previsto": 0.0, "metodo": "sem_dados",
            "observacao": "Não há sessões para treinar o modelo.",
        }], columns=colunas)

    base = pd.DataFrame({"data": [s.inicio.date() for s in sessoes], "kwh": [max(float(s.kwh), 0.0) for s in sessoes]})
    diario = base.groupby("data")["kwh"].sum().sort_index()
    idx = pd.date_range(start=pd.Timestamp(min(diario.index)), end=pd.Timestamp(max(diario.index)), freq="D")
    diario.index = pd.to_datetime(diario.index)
    diario = diario.reindex(idx, fill_value=0.0).astype(float)

    historico = diario.to_list()
    datas = list(diario.index)
    metodo = "RandomForestRegressor"
    if len(historico) < 10:
        metodo = "media_movel_7_dias"
        previsoes = []
        for i in range(dias):
            prox = datas[-1] + pd.Timedelta(days=i + 1)
            janela = historico[-7:] or [0.0]
            valor = sum(janela) / len(janela)
            previsoes.append({"tipo": "previsao", "data": prox.strftime("%Y-%m-%d"),
                              "kwh_previsto": round(max(valor, 0.0), 3), "metodo": metodo,
                              "observacao": "Histórico curto; estimativa pela média dos últimos 7 dias."})
            historico.append(valor)
        return pd.DataFrame(previsoes, columns=colunas)

    def linha_features(data, serie):
        ultimos = serie[-7:]
        return [data.dayofweek, data.day, data.month, serie[-1],
                serie[-7] if len(serie) >= 7 else serie[-1], sum(ultimos) / len(ultimos)]

    X, y = [], []
    for i in range(7, len(historico)):
        X.append(linha_features(datas[i], historico[:i]))
        y.append(historico[i])
    modelo = RandomForestRegressor(n_estimators=120, max_depth=5, random_state=42)
    modelo.fit(X, y)
    previsoes = []
    for i in range(dias):
        prox = datas[-1] + pd.Timedelta(days=1)
        # Datas futuras são calculadas sequencialmente; a previsão alimenta a próxima janela.
        valor = max(float(modelo.predict([linha_features(prox, historico)])[0]), 0.0)
        previsoes.append({"tipo": "previsao", "data": prox.strftime("%Y-%m-%d"),
                          "kwh_previsto": round(valor, 3), "metodo": metodo,
                          "observacao": "Estimativa, não é medição real."})
        historico.append(valor)
        datas.append(prox)
    return pd.DataFrame(previsoes, columns=colunas)


def executar(pasta_uso: Path, pasta_saida: Path, dias: int = 7) -> int:
    try:
        resultado = UsoSource().ler(pasta_uso)
    except ErroLeitura as exc:
        print(f"[ERRO] Não foi possível ler os CSVs: {exc}")
        return 1

    anomalias = detectar_anomalias(resultado.sessoes)
    previsoes = prever_uso_diario(resultado.sessoes, dias)
    pasta_saida.mkdir(parents=True, exist_ok=True)
    saida = pasta_saida / "relatorio_ia.csv"
    linhas = []
    for _, r in anomalias.iterrows():
        linhas.append({"tipo": r["tipo"], "data": r["inicio"], "sessao_id": r["sessao_id"],
                       "usuario_id": r["usuario_id"], "kwh": r["kwh"], "kwh_previsto": "",
                       "score_ia": r["score_ia"], "metodo": "Análise estatística e regras", "observacao": r["motivo"]})
    for _, r in previsoes.iterrows():
        linhas.append({"tipo": r["tipo"], "data": r["data"], "sessao_id": "", "usuario_id": "",
                       "kwh": "", "kwh_previsto": r["kwh_previsto"], "score_ia": "",
                       "metodo": "Previsão de consumo", "observacao": r["observacao"]})
    pd.DataFrame(linhas, columns=["tipo", "data", "sessao_id", "usuario_id", "kwh", "kwh_previsto",
                                  "score_ia", "metodo", "observacao"]).to_csv(saida, index=False, sep=";", encoding="utf-8-sig")

    print(f"Arquivos lidos: {len(resultado.arquivos)} | sessões analisadas: {len(resultado.sessoes)}")
    print(f"Anomalias sinalizadas: {len(anomalias)}")
    if not anomalias.empty:
        for _, r in anomalias.head(10).iterrows():
            inicio = pd.to_datetime(r["inicio"]).strftime("%d/%m/%Y %H:%M")
            print(
                f"  Sessão {r['sessao_id']} | Usuário {r['usuario_id']} | {inicio}\n"
                f"    Consumo: {r['kwh']:.3f} kWh | Duração: {r['duracao_min']} min\n"
                f"    Motivo: {r['motivo']}"
            )
    print(f"\nPrevisão de consumo para os próximos {dias} dias (estimativa em kWh):")
    exibicao = previsoes[["data", "kwh_previsto"]].rename(columns={
        "data": "Data", "kwh_previsto": "Consumo previsto (kWh)"
    }).copy()
    exibicao["Data"] = pd.to_datetime(exibicao["Data"], errors="coerce").dt.strftime("%d/%m/%Y").fillna("Sem data")
    print(exibicao.to_string(index=False))
    print(f"\nRelatório salvo em: {saida}")
    return 0


def main(argv: list[str]) -> int:
    pasta_uso = Path(argv[1]).resolve() if len(argv) > 1 else PASTA_USO_PADRAO
    pasta_saida = Path(argv[2]).resolve() if len(argv) > 2 else PASTA_SAIDA_PADRAO
    dias = int(argv[3]) if len(argv) > 3 else 7
    return executar(pasta_uso, pasta_saida, dias)


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except ValueError as exc:
        print(f"[ERRO] Parâmetro inválido: {exc}")
        raise SystemExit(2)
