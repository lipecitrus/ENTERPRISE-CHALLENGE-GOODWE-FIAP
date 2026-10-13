# IA simples para previsão de uso e detecção de anomalias — EV ChargeOps

O módulo `ia_uso.py` acrescenta uma análise experimental aos CSVs veiculares já usados pelo projeto. Ele reutiliza `UsoSource` em `leitor_uso.py` e lê a pasta `uso_carregador/` criada por `gerar_uso_carregador.py`.

## O que faz

- **Detecção de anomalias:** combina `IsolationForest` com regras determinísticas e explicáveis. Além de medidor, duração, potência e identificação, verifica SOC fora de 0%–100%, queda de SOC enquanto a energia acumulada aumenta, sessão sem agendamento associado, início fora da janela da reserva e reserva criada com menos de 60 minutos de antecedência.
- **Previsão de uso:** agrega o consumo em kWh por dia e usa `RandomForestRegressor` com atributos de calendário e defasagens do consumo. Se o histórico tiver menos de 10 dias, usa uma média móvel dos últimos 7 dias, evitando treinar um modelo complexo com poucos exemplos.
- **Relatório:** grava `fatura_saida/relatorio_ia.csv` com alertas e previsões.

## Acesso pelo painel do gestor

Após instalar as dependências abaixo, inicie `python main.py`, entre no **Painel do gestor** e selecione **Análise de IA (anomalias e previsão)**. A opção executa a análise para os CSVs de `uso_carregador/`, apresenta um resumo no terminal e salva `fatura_saida/relatorio_ia.csv`. Se preferir, a execução independente abaixo continua disponível.

## Instalação e execução

Na raiz do projeto:

```bash
pip install -r requirements.txt
python gerar_uso_carregador.py --seed 5
python ia_uso.py
```

Parâmetros opcionais:

```bash
python ia_uso.py uso_carregador fatura_saida 14
```

O exemplo acima lê a pasta `uso_carregador`, salva o relatório em `fatura_saida` e prevê 14 dias. Também é possível passar caminhos absolutos.

## Testes

```bash
python -m unittest discover -s tests -v
```

O teste `tests/test_ia_uso.py` cobre previsão com histórico suficiente, fallback com histórico curto, ausência de sessões, identificação, SOC fora do intervalo, SOC incoerente, sessões sem agendamento, reservas criadas com pouca antecedência e início fora da janela reservada.

## Limitações e uso responsável

- A previsão é exploratória: a qualidade depende de histórico suficiente, representativo e correto. Dados sintéticos servem para demonstrar o fluxo, mas não comprovam precisão operacional.
- `IsolationForest` sinaliza pontos estatisticamente incomuns, não prova fraude nem defeito. Revisar os alertas antes de qualquer decisão.
- O SOC é validado quanto ao intervalo físico de 0% a 100% e a inconsistências temporais simples. Como o CSV não contém a capacidade nominal da bateria por veículo, a versão não calcula ainda a coerência quantitativa entre kWh e variação percentual do SOC.
- Sessões avulsas são permitidas pelo domínio e aparecem como alerta para revisão; isso não significa automaticamente uso indevido. A regra de antecedência de 60 minutos é uma premissa operacional configurável/documentada, não uma lei universal.
- A versão atual analisa características agregadas por sessão; não é um detector certificado de falhas elétricas nem um sistema de segurança.
- O módulo não altera CSVs de origem, não modifica regras de cobrança e não bloqueia sessões. A fatura oficial continua sob responsabilidade de `src/rateio`.
