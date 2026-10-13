# EV ChargeOps — Documentação técnica

**Leitura de uso de carregadores veiculares e faturamento mensal**

## 1. Objetivo e decisões de escopo

O EV ChargeOps simula o registro de sessões de recarga de veículos elétricos, interpreta os registros CSV e calcula cobranças mensais por usuário/unidade. A solução foi modelada com eventos próprios de carregamento veicular (início, medições, carro cheio, fim e eventos de reserva).

A estrutura de dados da Goodwe foi descartada. O formato anterior não representava adequadamente o domínio pretendido: dados de um carregador veicular, suas sessões, medidor de energia, autenticação, reservas e fila. A entrada atual é o conjunto de CSVs `uso_*.csv` gerados por `gerar_uso_carregador.py`; não se deve presumir compatibilidade sem adaptação com exportações Goodwe.

## 2. Arquitetura e fluxo de dados

```text
                         ┌──────────────────────────┐
                         │          main.py         │
                         │ CLI: cadastro, login,    │
                         │ reservas, sessões, fatura│
                         │ e painel do gestor       │
                         └────────────┬─────────────┘
                                      │ dados operacionais
                                      ▼
                           ev_chargeops.xlsx
                         (persistência local Excel)

gerar_uso_carregador.py ──gera──> uso_carregador/uso_*.csv
                                      │
                    ┌─────────────────┴─────────────────┐
                    ▼                                   ▼
             leitor_uso.py                         ia_uso.py
       normaliza e valida dados              análise experimental
                    │                         ├─ IsolationForest
                    ▼                         └─ RandomForestRegressor
            calcular_fatura.py                         │
                    │                                  │
                    ▼                                  ▼
               src/rateio/                      relatorio_ia.csv
        ├─ parametros.py                            (relatório)
        ├─ regras.py
        ├─ validacoes.py
        ├─ fatura.py
        └─ saida.py
                    │
                    ▼
               fatura_saida/
        ├─ fatura_mensal.csv
        ├─ detalhe_sessoes.csv
        ├─ avisos.txt
        ├─ fatura_mensal.xlsx (exportação da aplicação)
        └─ relatorio_ia.csv
```

A aplicação interativa (`main.py`) e o pipeline analítico baseado em CSV são fluxos relacionados ao mesmo domínio, mas não devem ser tratados como uma integração transacional única. A persistência operacional do aplicativo é feita em `ev_chargeops.xlsx`; a leitura de sessões e o rateio usam os CSVs em `uso_carregador/`. A correspondência entre reservas/liberações do aplicativo e os registros de consumo CSV deve ser verificada antes de interpretar uma fatura como conciliada de ponta a ponta.

### Responsabilidade dos módulos

- `main.py`: interface de linha de comando interativa do EV ChargeOps. Oferece cadastro e login de moradores, agendamento/cancelamento de reservas, início e encerramento de uso, consulta de fatura e painel do gestor com resumo, liberações, agenda e exportação Excel. Mantém dados operacionais em `ev_chargeops.xlsx`.
- `gerar_uso_carregador.py`: gera dados sintéticos reproduzíveis, com uma linha de evento/medição por registro e um CSV por usuário; aceita semente e injeção de anomalias.
- `leitor_uso.py`: camada de ingestão. Lê CSVs, reconhece variações de cabeçalho, delimitador e codificação, normaliza números/datas, elimina duplicatas e monta sessões, leituras e reservas. **Não calcula valores de cobrança.**
- `src/rateio/contrato.py`: ponto de integração entre a leitura e o faturamento.
- `src/rateio/parametros.py`: carrega e valida tarifas e taxas, sem exigir que os valores fiquem hard-coded no código.
- `src/rateio/regras.py`: funções isoladas para faixa horária, energia, ociosidade, sessão sem reserva e no-show.
- `src/rateio/validacoes.py`: verifica consistência entre reservas, medidor, sessões e dados conciliados; emite avisos para análise.
- `src/rateio/fatura.py`: coordena as regras e produz `ResultadoRateio`, `Fatura` e `CobrancaSessao`.
- `src/rateio/saida.py`: grava os resultados para consumo posterior por painel/app ou revisão manual.
- `calcular_fatura.py`: interface de linha de comando; delega o cálculo ao pacote `src.rateio`.
- `ia_uso.py`: módulo opcional de análise exploratória. Reutiliza `UsoSource`, sinaliza sessões estatisticamente incomuns com `IsolationForest` e regras complementares, e prevê consumo diário com `RandomForestRegressor` quando há histórico suficiente. Não altera os CSVs de origem nem a fatura oficial.
- `requirements.txt`: dependências do projeto (pandas e openpyxl para o aplicativo e o rateio; scikit-learn para o módulo de IA).
- `tests/test_rateio.py`: testes do rateio, regras, validações e CLI.
- `tests/test_ia_uso.py`: testes específicos de previsão, histórico curto, ausência de sessões e sessões sem identificação.
- `tests/test_main.py`: testes da validação do CPF no cadastro da aplicação de terminal.

### Modelo de dados principal

- **Leitura**: instante, energia acumulada em kWh e, quando disponível, potência, estado de carga (SoC) e indicador de fila.
- **Sessao**: agrupa eventos pelo `sessao_id`; contém usuário, unidade, identificação, início/fim, fim da carga, estado e leituras.
- **Reserva**: id e horários de início/fim/criação.
- **EventoReserva**: reserva cancelada ou não utilizada.
- **UsoUsuario**: agrega sessões e eventos por usuário.
- **ResultadoLeitura**: conjunto de usuários, sessões, reservas, eventos, arquivos lidos e avisos.
- **CobrancaSessao / Fatura**: valores calculados e totais por competência mensal.

## 3. Estrutura dos CSVs e diretório de saída

Ao executar `gerar_uso_carregador.py` sem `--saida`, os CSVs são gravados numa **subpasta chamada `uso_carregador` ao lado do próprio script**. Não são gravados soltos na raiz. O gerador cria a pasta automaticamente (`mkdir(..., exist_ok=True)`).

Exemplo esperado:

```text
ENTERPRISE-CHALLENGE-GOODWE-FIAP-main/
├── gerar_uso_carregador.py
├── leitor_uso.py
├── calcular_fatura.py
├── config/parametros_rateio.csv
├── uso_carregador/
│   ├── uso_U01_ana_beatriz_souza.csv
│   ├── uso_U02_ricardo_mendes.csv
│   └── ...
└── fatura_saida/
```

O leitor sem argumentos usa por padrão `uso_carregador` ao lado de `leitor_uso.py`. Quando recebe uma pasta, procura apenas arquivos `.csv` cujo nome comece com `uso_`. Também aceita um caminho direto para um único CSV. Assim, o caminho padrão do gerador e o do leitor estão alinhados.

Colunas centrais do formato: `timestamp`, `evento`, `usuario_id`, `sessao_id` e `energia_acumulada_kwh`. O leitor exige essas colunas; as demais podem estar ausentes e serão tratadas como vazias, com aviso. A energia é um **registrador acumulado**: o consumo da sessão é a diferença entre a última e a primeira leitura válida, não a soma dos valores do registrador.

O leitor tolera cabeçalhos com variações comuns, delimitadores vírgula/ponto e vírgula/tabulação/barra vertical, UTF-8/UTF-16 com BOM e cp1252, formatos de data suportados, linhas vazias e duplicadas. Em pasta com múltiplos CSVs, um arquivo inválido pode ser ignorado com aviso; se nenhum arquivo puder ser lido, ocorre `ErroLeitura`. Os arquivos de origem não são alterados.

## 4. Regras de cobrança

Os valores são configurados em `config/parametros_rateio.csv`. Um arquivo `parametros_rateio.csv` dentro da pasta de uso pode sobrescrever os parâmetros que declarar. Valores atuais do projeto:

| Regra/parâmetro | Valor padrão | Aplicação |
|---|---:|---|
| Energia fora de ponta | R$ 0,85/kWh | Tarifa por energia alocada à faixa |
| Energia intermediária | R$ 1,20/kWh | Tarifa por energia alocada à faixa |
| Energia ponta | R$ 1,70/kWh | Tarifa por energia alocada à faixa |
| Horário de ponta | 18h, 19h e 20h | Horas cheias em dias úteis, exceto feriados configurados |
| Horário intermediário | 17h e 21h | Horas cheias em dias úteis, exceto feriados configurados |
| Antecedência mínima | 60 minutos | Cancelamento posterior ao limite pode gerar no-show; reserva feita muito perto do início gera aviso |
| Carência de ociosidade | 15 minutos | Período gratuito após o fim da carga |
| Bloco de ociosidade | 30 minutos | Cada bloco iniciado é contado |
| Taxa por bloco | R$ 2,00 | Só quando há outro usuário na fila no intervalo considerado |
| Teto de ociosidade | R$ 20,00/sessão | Limita a cobrança de ociosidade por sessão |
| Sessão sem reserva | R$ 1,50 | Taxa fixa por sessão avulsa |
| No-show | R$ 5,00 | Reserva não utilizada ou cancelamento tardio elegível |
| Custo fixo por unidade | R$ 15,00/mês | Incluído na fatura de cada usuário/unidade registrada |

### Como as regras são aplicadas

1. **Energia por faixa horária:** para cada par de leituras consecutivas, calcula-se a variação positiva do registrador e atribui-se essa energia à faixa correspondente ao ponto médio do intervalo. Se houver menos de duas leituras, usa-se a faixa do início como fallback, com aviso de confiabilidade.
2. **Ociosidade com fila:** conta o tempo após `fim_carga + carência` até o fim da sessão, considerando intervalos cuja leitura final indica `fila_espera = 1`. Cada bloco iniciado é cobrado, limitado ao teto por sessão. Sessões encerradas por `PowerLoss` não recebem cobrança de ociosidade.
3. **Sessão sem reserva:** se não houver reserva/agendamento associado, aplica-se a taxa de sessão avulsa. O mesmo vale para sessão que começa depois do fim da janela da reserva (a reserva não vale mais); nesse caso sai também um aviso.
4. **No-show:** evento `ReservaNaoUtilizada` gera cobrança. `ReservaCancelada` só gera cobrança se o cancelamento ocorrer depois do limite de antecedência em relação ao início da reserva. Sem horário de início conhecido, o sistema não presume cancelamento tardio.
5. **Sessão não identificada:** sessão sem usuário, com usuário não cadastrado ou sem identificação não é atribuída à fatura de uma pessoa. Sua energia é calculada e apresentada separadamente em `NAO_IDENTIFICADO`, sem taxa de sessão avulsa ou ociosidade.
6. **Custo fixo:** é incluído na fatura mensal de cada usuário/unidade criado a partir dos dados lidos.
7. **Competência:** por padrão, é o mês do início da sessão ou da reserva. Uma sessão que atravesse a virada do mês pertence ao mês em que começou. Dados misturados geram aviso; a competência pode ser definida explicitamente pela API.
8. **Arredondamento:** os componentes monetários de cada cobrança são arredondados a centavos no momento em que a cobrança é criada (arredondamento meio para cima). A fatura soma os valores já arredondados, garantindo que o detalhe feche com o total.

Fórmula conceitual do total da fatura:

`total = energia + ociosidade + taxa_sem_reserva + no_show + custo_fixo`

Os avisos são parte importante da auditoria: dados inconsistentes não devem ser silenciosamente interpretados como certeza. Casos com medidor decrescente, poucas leituras, sessões sobrepostas ou dados de reserva insuficientes devem ser revisados antes de tratar a fatura como definitiva.

## 5. Como executar

Execute os comandos a partir da pasta raiz do projeto, onde estão `gerar_uso_carregador.py` e `calcular_fatura.py`. Use Python 3.10 ou superior (o código usa anotações de tipos modernas) e não há dependências externas declaradas para o fluxo principal.

### 5.1 Gerar os dados de teste

```bash
python gerar_uso_carregador.py --seed 5
```

Saída padrão: subpasta `uso_carregador/`. A semente fixa torna os dados reproduzíveis. Para gerar dados com problemas intencionais:

```bash
python gerar_uso_carregador.py --seed 5 --anomalias
```

Para escolher outro diretório:

```bash
python gerar_uso_carregador.py --seed 5 --saida ./dados_teste
```

### 5.2 Rodar somente o leitor

```bash
python leitor_uso.py
```

O comando lê `./uso_carregador` em relação à localização do script, imprime um resumo por usuário e mostra avisos. Também aceita uma pasta explícita ou um CSV individual:

```bash
python leitor_uso.py uso_carregador
python leitor_uso.py uso_carregador/uso_U01_ana_beatriz_souza.csv
python leitor_uso.py ./dados_teste
```

Para importar o leitor em outro módulo:

```python
from leitor_uso import UsoSource

resultado = UsoSource().ler("uso_carregador")
print(len(resultado.sessoes))
print(resultado.avisos)
```

### 5.3 Calcular e gravar as faturas

```bash
python calcular_fatura.py
```

Por padrão, lê `uso_carregador/` e grava em `fatura_saida/`. Para definir os diretórios:

```bash
python calcular_fatura.py ./uso_carregador ./fatura_saida
```

Alternativa equivalente:

```bash
python -m src.rateio ./uso_carregador ./fatura_saida
```

Os arquivos de saída são `fatura_mensal.csv` (totais por usuário e competência), `detalhe_sessoes.csv` (componentes por sessão/no-show e sessões não identificadas) e `avisos.txt` (validações e anomalias).

## 6. Módulo experimental de inteligência artificial

O módulo `ia_uso.py` é uma camada analítica opcional e separada do cálculo financeiro. Foi acrescentado para demonstrar duas capacidades de aprendizado de máquina usando os dados de uso de carregadores veiculares. A análise pode ser iniciada no painel autenticado do gestor, pela opção **Análise de IA (anomalias e previsão)**, ou diretamente pela linha de comando. A importação da IA ocorre sob demanda, para que a aplicação principal continue iniciando sem carregar `scikit-learn` quando a opção não for utilizada.

### 6.1 Detecção de anomalias

O algoritmo `IsolationForest` analisa características derivadas das sessões e sinaliza observações que diferem do padrão estatístico observado. Em paralelo, regras determinísticas verificam energia acumulada negativa, duração inválida, potência média elevada, identificação incompleta, SOC fora do intervalo de 0% a 100%, queda relevante de SOC enquanto o medidor acumulado aumenta, início fora da janela da reserva e reservas criadas com menos de 60 minutos de antecedência. O relatório registra a categoria, a pontuação estatística disponível e a justificativa do alerta. Sessão avulsa (sem reserva) é permitida e paga a taxa, então não gera alerta.

Um alerta significa apenas que o registro merece revisão. Não comprova fraude, falha elétrica ou comportamento indevido; os resultados dependem da qualidade e representatividade dos dados. Como o formato atual não informa a capacidade nominal da bateria de cada veículo, o módulo ainda não calcula a coerência quantitativa entre kWh transferidos e variação do SOC. Essa validação exige cadastro confiável da capacidade e tolerância para perdas, arredondamentos e estimativas do BMS.

### 6.2 Previsão de consumo

O consumo é agregado por dia. Com histórico suficiente (a implementação utiliza o limiar de dez dias), o módulo emprega `RandomForestRegressor` com atributos de calendário e defasagens do consumo. Com histórico curto, utiliza um fallback baseado na média móvel dos últimos sete dias. 

### 6.3 Instalação e execução

O fluxo principal de cadastro e faturamento não precisa carregar o pacote de IA. Para usar a opção de análise no painel do gestor, instale as dependências opcionais e gere ou disponibilize os CSVs:

```bash
pip install -r requirements.txt
python gerar_uso_carregador.py --seed 5
python ia_uso.py
```

Para indicar a pasta de entrada, pasta de saída e horizonte de previsão (em dias):

```bash
python ia_uso.py uso_carregador fatura_saida 14
```

O relatório é gravado em `fatura_saida/relatorio_ia.csv`. A execução da IA não modifica a fatura oficial, não altera os arquivos de origem e não bloqueia carregamentos.

## 7. Testes automatizados

Execute na raiz do repositório:

```bash
python -m unittest discover -s tests -v
```

O conjunto `tests/test_rateio.py` cobre parâmetros, regras isoladas, competência, dados de aceitação com semente fixa, anomalias, propriedades em várias sementes e execução da CLI. Os casos incluem classificação por faixa horária, cálculo do kWh pelo registrador, ociosidade e teto, taxa sem reserva, no-show/cancelamento, arredondamento, sessões não identificadas, conciliação dos totais e arquivos de saída. O conjunto `tests/test_ia_uso.py` verifica cenários da análise de IA, incluindo histórico suficiente ou curto, ausência de sessões, identificação incompleta, SOC fora de 0%–100%, regressão incoerente do SOC, sessão avulsa sem alerta, reserva com antecedência inferior a 60 minutos e sessão fora da janela reservada.


