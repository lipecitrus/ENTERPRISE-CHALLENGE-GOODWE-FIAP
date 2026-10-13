# ENTERPRISE CHALLENGE 2026 — GOODWE + FIAP

**SPRINT 02: O desenvolvimento do projeto** 

Grupo 11: Filipe Augusto Chaves (rm570827), Yury Alexander Tavares (rm572825), Murillo Gomes de Almeida (rm572196), Arthur Henrique Ruiz Ramos (rm568738)

>Enterprise Challenge 2026  
>Aplicação em Python para cadastro de moradores, reservas, registro de sessões de carregamento, rateio de custos, geração de faturas e análise com o uso de IA.


## 1. Visão geral

O EV ChargeOps é um protótipo de sistema para administrar a utilização compartilhada de carregadores de veículos elétricos em ambientes como condomínios, edifícios corporativos ou campus. O problema tratado é operacional: vários usuários compartilham uma quantidade limitada de carregadores, e o administrador precisa saber quem utilizou o equipamento, quando ocorreu a recarga, qual foi o consumo, se houve reserva e como distribuir os custos de forma rastreável.

A solução combina uma aplicação de terminal, armazenamento simples em Excel, arquivos CSV de sessões de recarga, um leitor que normaliza os eventos, um módulo independente de rateio e uma camada experimental de análise com aprendizado de máquina.

## 2. Relação com a Sprint 01 e justificativa dos desvios

A pesquisa, a arquitetura e o modelo de rateio definidos na Sprint 01 estão em [`docs/README_SPRINT_1.md`](docs/README_SPRINT_1.md). Esta seção compara o que foi planejado lá com o que foi implementado e justifica cada mudança.

### 2.1 O que foi implementado conforme o planejado

| Planejado na Sprint 01 | Onde está na Sprint 02 |
|---|---|
| Registrar sessões de recarga por usuário (início, fim, duração, kWh) | `leitor_uso.py` reconstrói as sessões a partir dos eventos e leituras do carregador |
| Calcular o consumo individual por unidade/apartamento e do condomínio como um todo | `src/rateio/fatura.py` agrega por usuário/unidade; `fatura_mensal.csv` traz o total geral |
| Rateio com cobrança por horário de uso (adicional no horário de pico) | Faixas fora de ponta, intermediária e ponta em `src/rateio/regras.py`, com valores em `config/parametros_rateio.csv` |
| Rateio considerando o agendamento da recarga | Taxa de sessão sem reserva e taxa de no-show/cancelamento tardio |
| Custo fixo por unidade (atributo `custo_fixo` da entidade Unidade) | Custo fixo mensal de R$ 15,00 por unidade |
| "Definição arbitrária dos valores unitários por margens de horário" (plano da Sprint 02) | Tarifas de demonstração parametrizadas em CSV, fora do código |
| "Desenvolver um aplicativo de agendamento dos pontos de recarga" (plano da Sprint 02) | `main.py`: cadastro, login, reservas em blocos de 30 minutos, cancelamento, liberação do carregador e painel do gestor |
| "IA na previsão de anomalias e de uso" (camada de aplicação) | `ia_uso.py`: detecção de anomalias (`IsolationForest` + regras) e previsão de consumo diário (`RandomForestRegressor`) |

### 2.2 Desvios em relação à Sprint 01

| Aspecto | Planejado na Sprint 01 | Implementado na Sprint 02 | Justificativa |
|---|---|---|---|
| Fonte dos dados | Dados do HCA G2 lidos via OCPP/MODBUS e organizados pela API SEMS da GoodWe | CSVs simulados por `gerar_uso_carregador.py`, no formato de eventos de um carregador (início, leituras do medidor, `CarroCheio`, fim, reservas) | Não houve acesso a dados reais do carregador nem à API SEMS durante a sprint, e a estrutura de dados GoodWe disponível como referência é voltada a inversores e armazenamento de energia: não traz sessões de recarga, identificação do usuário, reservas nem fila. O simulador reproduz os eventos que o HCA G2 gera via OCPP/MODBUS (por exemplo, `CarroCheio` equivale ao `SuspendedEV` do OCPP), e a especificação em [`docs/ESPECIFICACAO_ARQUIVOS_USO.md`](docs/ESPECIFICACAO_ARQUIVOS_USO.md) indica como mapear uma exportação real do SEMS+ para as mesmas colunas. Com isso, o leitor, o rateio e a IA não precisam mudar quando houver dados reais. |
| Cobrança por tempo | "Cobrança adicional a cada 30 minutos" de tempo de carregamento | Cobrança de R$ 2,00 por bloco de 30 minutos de **ociosidade** (veículo conectado depois de a carga terminar), com 15 minutos de carência, só quando há outro usuário na fila e com teto de R$ 20,00 por sessão | Durante o carregamento, o usuário já paga pela energia em kWh; cobrar também pelo tempo de carga penalizaria duas vezes quem tem um veículo que carrega mais devagar. O problema operacional real é o veículo que termina de carregar e continua ocupando o ponto enquanto outro morador espera. A regra de ociosidade ataca esse comportamento sem encarecer a recarga em si. |
| Interface | "Interface gráfica amigável para usuários e gestores" | Aplicação de terminal (`main.py`) | O foco da sprint foi a lógica de sessões, rateio e IA, que é o núcleo exigido do protótipo. Uma interface de terminal permitiu demonstrar o fluxo completo (cadastro, reserva, liberação, fatura e painel do gestor) sem depender de servidor web ou framework gráfico. As funções de cálculo ficam em módulos separados (`src/rateio/`, `ia_uso.py`) e podem ser reaproveitadas por uma interface gráfica no futuro. |
| Persistência | Banco de dados com usuários, unidades, carregadores, sessões e faturas | Excel (`ev_chargeops.xlsx`) para os dados do aplicativo; CSVs para a telemetria; CSV/Excel para as faturas | Excel e CSV são fáceis de inspecionar e não exigem instalar um servidor de banco de dados para avaliar o protótipo. A limitação está registrada na seção 12. |
| Modelo de dados | Entidades Usuário, Unidade, Carregador, Veículo, Sessão e Fatura | Abas `usuarios`, `agendamentos` e `liberacoes` no aplicativo; veículo, sessão e leituras nos CSVs de uso; fatura e detalhe por sessão nas saídas do rateio | **Agendamento** foi acrescentado porque o modelo de rateio depende de reservas (sessão sem reserva, no-show, cancelamento tardio). **Carregador** não virou tabela porque o protótipo simula um único ponto de recarga (o HCA G2 do Energy Innovation Lab). **Unidade** é representada pelo campo `unidade_id` do usuário, já que cada unidade tem um único cadastro. **Veículo** aparece nos dados de uso de cada usuário, mas não é cadastrado no aplicativo, pois não influencia o valor cobrado. |
| Fluxo sessão → fatura | Eventos salvos no perfil do usuário na API SEMS e cobrança gerada a partir deles | O aplicativo e os CSVs de uso são fontes separadas: reservas feitas no menu não alteram os CSVs usados no rateio | Sem acesso ao carregador real, não é possível gerar leituras de medidor a partir de uma liberação feita no menu. A separação foi mantida explícita, e o painel do gestor e a fatura usam o mesmo cálculo de `src/rateio/`. |

## 3. Funcionalidades

### Morador

- Cadastro com nome, CPF, unidade e senha.
- Login usando CPF e senha.
- Consulta e cancelamento de agendamentos.
- Criação de reservas em blocos de 30 minutos, com duração máxima de 120 minutos, respeitando as regras configuradas.
- Início e encerramento de utilização do carregador no protótipo.
- Consulta da fatura mensal associada aos registros disponíveis.

### Gestor

- Acesso a um painel administrativo protegido por senha definida no primeiro acesso.
- Consulta do resumo de rateio.
- Visualização dos registros de liberações e reservas.
- Exportação da fatura em formato Excel com abas `faturas` e `detalhe`.

### Processamento de dados

- Geração de CSVs sintéticos de utilização.
- Leitura e reconstrução de sessões a partir dos eventos e leituras dos CSVs.
- Validação de dados e emissão de avisos.
- Cálculo parametrizado de energia, ociosidade, uso sem reserva, no-show e custo fixo.
- Exportação do rateio em CSV e avisos em texto.

### IA experimental

- Sinalização de sessões estatisticamente atípicas e de problemas detectáveis por regras simples.
- Previsão exploratória do consumo diário para os próximos dias.
- Exportação de relatório próprio, sem modificar as faturas ou os dados de entrada.

## 4. Arquitetura

O projeto é dividido por responsabilidades, ainda que a interface de operação seja uma aplicação de terminal.

```text
Usuário / Gestor
       |
       v
    main.py ----------------------> ev_chargeops.xlsx
       |                            (cadastros, reservas,
       |                             liberações e configuração)
       |
       +-------------------------------+
                                       |
Gerador de dados                      | CSVs de uso
gerar_uso_carregador.py --------------> uso_carregador/*.csv
                                       |
                                       v
                                  leitor_uso.py
                                  (UsoSource)
                                       |
                       +---------------+----------------+
                       |                                |
                       v                                v
                src/rateio/                         ia_uso.py
             validação e cobrança             anomalias e previsão
                       |                                |
                       v                                v
                 fatura_saida/                    fatura_saida/
             CSVs, avisos e Excel                 relatorio_ia.csv
```

### Principais módulos

- **`main.py`** — interface de terminal, cadastro, autenticação, reservas, liberação do carregador, consulta de fatura e ações do gestor. Usa pandas para ler e gravar o Excel do aplicativo.
- **`gerar_uso_carregador.py`** — cria cenários sintéticos e escreve arquivos CSV de eventos/leituras. Por padrão, cria `uso_carregador/` ao lado do próprio script.
- **`leitor_uso.py`** — contém o contrato de dados e `UsoSource`, responsável por interpretar CSVs, normalizar campos e reconstruir usuários, sessões, leituras e eventos de reserva. Também pode ser executado diretamente para exibir um resumo.
- **`src/rateio/contrato.py`** — expõe os tipos e contratos utilizados pelo leitor e pelo rateio.
- **`src/rateio/validacoes.py`** — executa verificações de consistência, continuidade de leituras e condições relacionadas às reservas.
- **`src/rateio/parametros.py`** — carrega tarifas e taxas de `config/parametros_rateio.csv`, aceitando substituições locais na pasta de uso.
- **`src/rateio/regras.py`** — implementa funções específicas para faixas tarifárias, custo de energia, ociosidade, uso sem reserva e no-show.
- **`src/rateio/fatura.py`** — coordena o cálculo das cobranças e agrega os resultados por usuário/unidade e sessão.
- **`src/rateio/saida.py`** — grava a fatura mensal, o detalhamento e os avisos.
- **`calcular_fatura.py`** — ponto de entrada por linha de comando para executar o rateio.
- **`ia_uso.py`** — camada analítica experimental que reutiliza o leitor para detectar anomalias e prever consumo diário.
- **`tests/`** — testes automatizados das regras de rateio e das funcionalidades da IA.

### Fluxo de dados

1. O gerador produz os CSVs específicos do cenário veicular.
2. O leitor percorre os arquivos da pasta indicada e reconstrói as sessões.
3. O rateio valida os registros, carrega os parâmetros e calcula as cobranças.
4. A camada de saída grava arquivos auditáveis para conferência.
5. Opcionalmente, o módulo de IA analisa as sessões e produz um relatório separado.

A IA não participa do cálculo da fatura oficial. Isso evita que uma estimativa ou um alerta probabilístico altere diretamente valores cobrados.

## 5. Estrutura de diretórios

```text
ENTERPRISE-CHALLENGE-GOODWE-FIAP/
├── README.md                    # este documento (Sprint 02)
├── requirements.txt             # dependências do projeto
├── main.py                      # aplicação de terminal (morador e gestor)
├── gerar_uso_carregador.py      # gerador dos CSVs de uso do carregador
├── leitor_uso.py                # leitura e reconstrução das sessões
├── calcular_fatura.py           # linha de comando do rateio
├── ia_uso.py                    # detecção de anomalias e previsão de uso
├── config/
│   └── parametros_rateio.csv    # tarifas e taxas
├── src/
│   └── rateio/
│       ├── __init__.py
│       ├── __main__.py
│       ├── contrato.py
│       ├── fatura.py
│       ├── parametros.py
│       ├── regras.py
│       ├── saida.py
│       ├── validacoes.py
│       └── README.md
├── tests/
│   ├── test_rateio.py
│   ├── test_ia_uso.py
│   └── test_main.py
├── docs/
│   ├── README_SPRINT_1.md           # pesquisa e planejamento da Sprint 01
│   ├── DOCUMENTACAO_TECNICA.md      # arquitetura e regras em detalhe
│   ├── ESPECIFICACAO_ARQUIVOS_USO.md# colunas e eventos dos CSVs de uso
│   ├── INTERFACE_TERMINAL.md        # menus e regras da aplicação de terminal
│   └── MODULO_IA.md                 # módulo de IA em detalhe
├── evidencias/                  # evidências de funcionamento (ver seção 14)
├── uso_carregador/              # criado pelo gerador; contém os CSVs de entrada
├── fatura_saida/                # criada durante a geração de relatórios
└── ev_chargeops.xlsx            # criado pelo main.py no primeiro uso
```

`uso_carregador/`, `fatura_saida/` e `ev_chargeops.xlsx` são gerados durante a execução e não ficam versionados no repositório. O arquivo `ev_chargeops.xlsx` armazena os dados da interface do aplicativo (cadastros, reservas, liberações e a senha do gestor, definida no primeiro acesso ao painel); ele não substitui os CSVs usados pelo módulo de rateio.

### Documentação complementar

- [`docs/README_SPRINT_1.md`](docs/README_SPRINT_1.md) — pesquisa das três frentes, arquitetura e modelo de rateio definidos na Sprint 01.
- [`docs/DOCUMENTACAO_TECNICA.md`](docs/DOCUMENTACAO_TECNICA.md) — arquitetura, fluxo de dados e regras de cobrança em detalhe.
- [`docs/ESPECIFICACAO_ARQUIVOS_USO.md`](docs/ESPECIFICACAO_ARQUIVOS_USO.md) — formato dos CSVs de uso do carregador.
- [`docs/INTERFACE_TERMINAL.md`](docs/INTERFACE_TERMINAL.md) — menus, regras de agendamento e roteiro de teste da aplicação.
- [`docs/MODULO_IA.md`](docs/MODULO_IA.md) — funcionamento e limitações do módulo de IA.
- [`src/rateio/README.md`](src/rateio/README.md) — organização interna do pacote de rateio.

## 6. Requisitos e instalação

- Python 3.10 ou superior recomendado.
- Dependências: `pandas` e `openpyxl` (aplicativo e rateio) e `scikit-learn` (módulo de IA), todas listadas em `requirements.txt`.

Abra um terminal na raiz do projeto, onde estão `main.py` e `gerar_uso_carregador.py`, e instale as dependências:

```bash
python -m pip install -r requirements.txt
```

A opção de IA no painel do gestor importa o módulo sob demanda: se o `scikit-learn` não estiver instalado, cadastro, reservas e rateio continuam funcionando e apenas a análise de IA fica indisponível.

> No Windows, se `python` não estiver associado à versão instalada, tente usar `py` no lugar do comando `python`.

## 7. Execução passo a passo

### 7.1 Gerar os CSVs de utilização

```bash
python gerar_uso_carregador.py --seed 5
```

Por padrão, o gerador grava os CSVs em `uso_carregador/`, uma subpasta ao lado do próprio script. O parâmetro `--seed 5` torna a geração reproduzível: executar novamente com a mesma semente e os mesmos parâmetros produz o mesmo cenário sintético.

Opções úteis:

```bash
python gerar_uso_carregador.py --help
python gerar_uso_carregador.py --mes 2026-09 --seed 5
python gerar_uso_carregador.py --seed 5 --anomalias
python gerar_uso_carregador.py --seed 5 --saida dados_teste
```

- `--mes AAAA-MM`: competência dos dados; o padrão atual é `2026-09`.
- `--seed N`: fixa a semente aleatória para reproduzir o cenário.
- `--anomalias`: injeta problemas de dados para testar as validações e os alertas.
- `--saida CAMINHO`: define a pasta de saída. Se for utilizado, os comandos seguintes devem apontar para essa pasta.

### 7.2 Executar o leitor isoladamente

```bash
python leitor_uso.py
```

O leitor utiliza `uso_carregador/` por padrão e exibe arquivos lidos, sessões por usuário, consumo em kWh, reservas e avisos.

Para indicar outra pasta:

```bash
python leitor_uso.py dados_teste
```

### 7.3 Calcular o rateio e gerar os arquivos financeiros

```bash
python calcular_fatura.py
```

O comando utiliza `uso_carregador/` como entrada e `fatura_saida/` como saída. É possível informar ambos os caminhos:

```bash
python calcular_fatura.py dados_teste resultado_teste
```

Alternativamente, o módulo pode ser executado como pacote:

```bash
python -m src.rateio
```

### 7.4 Iniciar a aplicação interativa

```bash
python main.py
```

No menu inicial, as opções são entrar como morador, cadastrar-se ou acessar o painel do gestor. Para uma demonstração completa, gere primeiro os CSVs, pois a consulta de fatura depende de registros de uso disponíveis.

**Importante:** o fluxo de cadastro/reserva/liberação da aplicação e o conjunto sintético de CSVs são fontes distintas no protótipo. Criar uma reserva no menu não reescreve automaticamente os CSVs sintéticos nem garante que aquela reserva seja refletida no cálculo do rateio. Para uma demonstração financeira consistente, utilize o conjunto de CSVs gerado e confira os avisos do leitor.

### 7.5 Executar a análise de IA

```bash
python ia_uso.py
```

Parâmetros posicionais opcionais: pasta de entrada, pasta de saída e quantidade de dias previstos.

```bash
python ia_uso.py uso_carregador fatura_saida 14
```

O exemplo lê `uso_carregador/`, grava em `fatura_saida/` e solicita previsão para 14 dias.

### 7.6 Executar os testes

```bash
python -m unittest discover -s tests -v
```

Execute a partir da raiz do projeto. Os testes verificam as regras do rateio e os cenários principais da IA.

## 8. Modelo de dados e arquivos gerados

### Arquivo do aplicativo: `ev_chargeops.xlsx`

O arquivo é lido e gravado por `main.py` e contém as abas:

- **`usuarios`** — CPF, identificador interno, nome, unidade e valor de verificação da senha.
- **`agendamentos`** — identificador da reserva, usuário, início, fim, status e indicador de cancelamento tardio.
- **`liberacoes`** — registro de utilização/liberação do carregador, identificação, reserva associada e horários.
- **`config`** — estrutura reservada a parâmetros do aplicativo.

O projeto usa Excel para simplificar a demonstração acadêmica; não é um banco de dados transacional multiusuário.

### CSVs de entrada: `uso_carregador/`

O gerador cria arquivos `uso_*.csv`, normalmente um arquivo por perfil/usuário e, quando aplicável, um arquivo de sessões não identificadas. Os registros descrevem eventos e leituras ao longo do tempo. `leitor_uso.py` é responsável por interpretar esses arquivos; portanto, o rateio e a IA devem utilizar o mesmo formato reconhecido pelo leitor.

Para a especificação detalhada das colunas, consulte [`docs/ESPECIFICACAO_ARQUIVOS_USO.md`](docs/ESPECIFICACAO_ARQUIVOS_USO.md).

### Saídas do rateio: `fatura_saida/`

- **`fatura_mensal.csv`** — totais agregados por usuário/unidade e competência, incluindo consumo por faixa horária e categorias de cobrança.
- **`detalhe_sessoes.csv`** — detalhamento por sessão e por cobrança, para rastrear a formação do total.
- **`avisos.txt`** — avisos de validação, inconsistências e casos que exigem conferência.
- **`fatura_mensal.xlsx`** — arquivo Excel exportado pelo painel do gestor, com abas `faturas` e `detalhe`.
- **`relatorio_ia.csv`** — relatório da execução de `ia_uso.py`, separado das faturas oficiais.

Os CSVs financeiros usam `;` como separador e vírgula como separador decimal. A saída da IA é gravada em UTF-8 com BOM para facilitar a abertura em ferramentas de planilha.

## 9. Regras de cobrança

As regras são implementadas em `src/rateio/` e os parâmetros ficam em `config/parametros_rateio.csv`. Os valores abaixo são os padrões presentes no repositório; podem ser ajustados pelo arquivo de configuração.

| Componente | Regra padrão |
|---|---|
| Energia fora de ponta | R$ 0,85 por kWh |
| Energia intermediária | R$ 1,20 por kWh |
| Energia na ponta | R$ 1,70 por kWh |
| Faixa de ponta | Dias úteis, horas configuradas como 18h, 19h e 20h |
| Faixa intermediária | Dias úteis, horas configuradas como 17h e 21h |
| Fins de semana e feriados listados | Fora de ponta durante todo o dia |
| Ociosidade | 15 minutos de carência após o fim da carga; cobra-se cada bloco iniciado de 30 minutos a R$ 2,00, apenas quando há fila, limitado a R$ 20,00 por sessão |
| Sessão sem reserva | R$ 1,50 por sessão avulsa |
| No-show | R$ 5,00 por reserva não utilizada ou cancelamento tardio elegível |
| Custo fixo | R$ 15,00 por mês por unidade |

### Como o total é calculado

De forma conceitual:

```text
Total = custo de energia
      + custo de ociosidade elegível
      + taxa de sessão sem reserva
      + cobranças de no-show
      + custo fixo mensal
```

O custo de energia é calculado por faixa horária, com base nos intervalos entre leituras. Para ociosidade, o sistema considera o tempo após o fim da carga e a carência, e só cobra os intervalos elegíveis em que há fila. Sessões interrompidas por `PowerLoss` não recebem cobrança de ociosidade. Reservas não utilizadas e cancelamentos tardios são tratados de acordo com os eventos reconhecidos pelo leitor e com a antecedência configurada.

As cobranças são arredondadas a centavos com regra decimal de meio para cima. Sessões sem usuário válido ou sem identificação adequada não devem ser atribuídas arbitrariamente a outro usuário: o sistema as reporta como não identificadas e mantém a situação visível para revisão.

### Alterar os parâmetros

Edite `config/parametros_rateio.csv`, mantendo as colunas `parametro`, `valor` e, opcionalmente, `descricao`. Um arquivo `parametros_rateio.csv` dentro da própria pasta de uso pode sobrescrever apenas os parâmetros ali declarados.

Após alterar tarifas ou taxas, execute novamente o rateio e revise os arquivos gerados. As tarifas são parâmetros de demonstração e não devem ser interpretadas como tarifas oficiais de uma concessionária.

## 10. Módulo experimental de IA

O módulo `ia_uso.py` acrescenta duas análises independentes da cobrança oficial. Ele pode ser executado diretamente ou pelo painel autenticado do gestor, na opção **Análise de IA (anomalias e previsão)**. Essa opção lê os CSVs da pasta `uso_carregador/` e grava `fatura_saida/relatorio_ia.csv`.

### Detecção de anomalias

- Usa **Isolation Forest** (`IsolationForest`) para sinalizar sessões com características estatisticamente incomuns.
- Complementa o modelo com verificações explícitas de energia negativa, duração inválida, potência elevada e identificação incompleta.
- Verifica SOC fora de 0%–100% e queda relevante do SOC enquanto o medidor acumulado aumenta.
- Sinaliza sessões sem agendamento, início fora da janela reservada e reservas criadas com menos de 60 minutos de antecedência. Sessões avulsas podem ser legítimas e ficam pendentes de conferência humana.
- Produz categorias e motivos de alerta para apoiar a revisão humana.

Um alerta significa que o registro merece análise; **não comprova fraude, defeito elétrico ou uso indevido**. A detecção depende da qualidade e representatividade dos dados. Como o CSV não informa a capacidade nominal da bateria por veículo, o módulo ainda não verifica a coerência quantitativa entre kWh e variação do SOC; essa extensão requer cadastro de capacidade e tolerâncias de medição/BMS.

### Previsão de uso

- Agrega o consumo das sessões em kWh por dia.
- Com histórico suficiente, usa `RandomForestRegressor` com atributos de calendário e defasagens do consumo.
- Com menos de dez dias de histórico, utiliza uma média móvel dos últimos sete dias como alternativa simples.
- Permite escolher o horizonte da previsão, por exemplo, sete ou 14 dias.

### Saída da IA

O arquivo `fatura_saida/relatorio_ia.csv` reúne os alertas de sessões e os valores previstos por dia, com método utilizado e observações. O módulo não altera CSVs de origem, não atualiza `ev_chargeops.xlsx`, não modifica `fatura_mensal.csv` e não bloqueia sessões.

## 11. Testes automatizados

O projeto utiliza a biblioteca padrão `unittest`.

```bash
python -m unittest discover -s tests -v
```

- **`tests/test_rateio.py`** — testa regras de cobrança, faixas tarifárias, validações, sessões identificadas/não identificadas e cálculo dos totais.
- **`tests/test_ia_uso.py`** — testa a previsão para o número de dias solicitado, o fallback para histórico curto, a sinalização de sessões sem identificação e o comportamento quando não existem sessões.
- **`tests/test_main.py`** — testa a validação do CPF no cadastro (dígitos verificadores, tamanho e dígitos repetidos).

Os testes automatizados ajudam a detectar regressões, mas não substituem testes com dados reais de carregadores, validação financeira por responsáveis nem homologação de segurança elétrica.

## 12. Decisões técnicas e limitações

### Decisões adotadas

- **CSV como formato de telemetria simulada:** simples de inspecionar, versionar e gerar em cenários repetíveis.
- **Leitor centralizado:** reduz a duplicação de parsing entre rateio e IA.
- **Parâmetros fora do código:** facilita a revisão das tarifas sem modificar as funções de regra.
- **Separação entre análise e cobrança:** mantém os resultados de IA como apoio, sem impacto automático no valor financeiro.
- **Testes automatizados:** permitem verificar regras críticas e casos de borda durante a evolução do projeto.

### Limitações conhecidas

- O gerador produz dados sintéticos; não há conexão com carregadores físicos, OCPP, APIs de fabricantes ou medidores reais.
- O Excel funciona como armazenamento local simplificado. Não oferece as garantias de concorrência, transações, permissões e auditoria de um banco de dados de produção.
- O fluxo de uso do menu e os CSVs sintéticos não estão integrados como um único serviço transacional. Reservas feitas no menu não alteram automaticamente os arquivos sintéticos utilizados pelo rateio.
- O armazenamento de senha usa hash, mas uma aplicação real exigiria controles adicionais, gestão de segredos, política de acesso e proteção de dados pessoais.
- A IA é demonstrativa, não certificada, e pode produzir falsos positivos ou previsões imprecisas.
- Não há cobrança financeira real, emissão fiscal, gateway de pagamento nem integração com concessionárias.

## 13. Solução de problemas

### “Não foram encontrados arquivos de uso” ou erro de leitura

1. Execute `python gerar_uso_carregador.py --seed 5`.
2. Confirme que os arquivos `.csv` estão em `uso_carregador/`.
3. Execute `python leitor_uso.py` para conferir se o leitor reconhece os arquivos.
4. Se utilizou `--saida`, passe essa pasta ao leitor, ao rateio e à IA.

### O módulo de IA não inicia

Instale as dependências adicionais:

```bash
python -m pip install -r requirements.txt
```

### A fatura apresenta avisos ou sessões não identificadas

Abra `fatura_saida/avisos.txt` e confira os registros no `detalhe_sessoes.csv`. Os avisos devem ser investigados; não atribua automaticamente consumo sem identificação a um morador.

### Quero testar registros anômalos

```bash
python gerar_uso_carregador.py --seed 5 --anomalias
python leitor_uso.py
python ia_uso.py
```

O parâmetro `--anomalias` injeta problemas de dados no conjunto sintético para exercitar as validações. Para voltar ao cenário padrão, gere novamente sem essa opção.

### Esqueci a senha do gestor

A senha do gestor fica gravada (em hash) na aba `config` de `ev_chargeops.xlsx`. Para defini-la novamente, apague essa linha da aba ou remova o arquivo `ev_chargeops.xlsx` (isso também apaga os cadastros e reservas feitos no aplicativo). No próximo acesso ao painel, o programa pede uma nova senha.

### Quero apagar os resultados e começar novamente

Os arquivos em `uso_carregador/` e `fatura_saida/` são dados de execução. Faça uma cópia se precisar preservá-los antes de removê-los ou regenerá-los. Evite apagar `ev_chargeops.xlsx` se quiser manter os cadastros criados na demonstração.

## 14. Evidências de funcionamento

As evidências estão na pasta [`evidencias/`](evidencias/), geradas executando o próprio código do repositório:

- [`evidencias/demonstracao.ipynb`](evidencias/demonstracao.ipynb) — notebook executado com o fluxo completo: dados de uso, leitura das sessões, rateio, composição da fatura, análise de IA, cenário com anomalias e testes.
- [`evidencias/sessao_terminal.txt`](evidencias/sessao_terminal.txt) — sessão real do `main.py`, do cadastro do morador até o painel do gestor.
- [`evidencias/dados/`](evidencias/dados/) — CSVs de entrada e arquivos de saída (fatura, detalhe por sessão, avisos e relatório da IA).

![Composição da fatura por unidade](evidencias/composicao_fatura.png)

## UTILIZACAO DA IA

Uso de IA: A ferramenta de IA foi utilizada nas seguintes etapas:

- Análise e desenvolvimento do projeto - para auxiliar na estruturação e funcionalidade do projeto, com supervisão da equipe.
- Documento ReadMe - para verificação ortográfica e auxílio na construção do texto, através da sugestão de palavras-chave.
