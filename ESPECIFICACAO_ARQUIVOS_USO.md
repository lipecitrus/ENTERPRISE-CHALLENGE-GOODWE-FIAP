# EV ChargeOps — Especificação dos arquivos de uso do carregador

Documento para quem vai implementar o **script de cálculo da fatura mensal**.
Explica cada coluna dos CSVs, como reconstruir as sessões e as regras de cobrança.

- Dados de exemplo: gerados por `gerar_uso_carregador.py` (**100% fictícios**).
- Implementação de referência do cálculo: `calcular_fatura.py` (pode ser usada para conferir resultados).

---

## 1. Visão geral

O carregador (HCA G2, via OCPP/MODBUS) registra o que acontece no ponto de recarga. Cada arquivo contém **o registro bruto de um único usuário durante o mês**. Os arquivos **não trazem** kWh por sessão, duração, nem valores em R$: tudo isso deve ser **derivado** pelo script de cálculo.

| Item | Valor |
| --- | --- |
| Arquivos | `uso_<usuario_id>_<nome>.csv`, um por usuário (ex.: `uso_U01_ana_beatriz_souza.csv`) |
| Estrutura | **Idêntica em todos os arquivos** (mesmas 15 colunas, mesma ordem) |
| Formato | CSV, UTF-8, separador **vírgula**, decimal com **ponto**, 1ª linha = cabeçalho |
| Datas/horas | `AAAA-MM-DD HH:MM:SS`, horário local do condomínio, sem fuso |
| Ordenação | linhas em ordem cronológica dentro de cada arquivo |
| Período | um mês inteiro (ex.: 01/09/2026 a 30/09/2026) |
| Carregador | **um único ponto de recarga compartilhado**; só uma sessão por vez |
| Cadastro | não há arquivo de cadastro: `usuario_id` e `unidade_id` vêm das linhas; o nome pode ser lido do nome do arquivo |

Arquivo extra (só nos testes com `--anomalias`): `uso_NAO_IDENTIFICADO.csv`, com a **mesma estrutura**, contendo sessões sem usuário.

**Dois "mundos" de informação.** O carregador mede energia e potência. O app de reservas sabe quem reservou e quando. Os arquivos juntam os dois: a reserva aparece na linha `Inicio` da sessão, e o campo `fila_espera` indica se havia outra pessoa na fila.

---

## 2. Colunas

| # | Coluna | Tipo / formato | Descrição | Usada no cálculo? |
| --- | --- | --- | --- | --- |
| 1 | `timestamp` | `AAAA-MM-DD HH:MM:SS` | Momento do evento/leitura. | **Sim** (duração, faixa horária, ociosidade) |
| 2 | `usuario_id` | texto, ex.: `U03` | Usuário identificado na sessão ou dono da reserva. **Vazio** só em sessão sem identificação. | **Sim** |
| 3 | `unidade_id` | texto `Bloco-Número`, ex.: `B-21` | Unidade (apartamento) do usuário. Vazio junto com `usuario_id`. | **Sim** (custo fixo, fatura por unidade) |
| 4 | `evento` | texto (ver seção 3) | Tipo da linha. | **Sim** |
| 5 | `sessao_id` | `S` + 4 dígitos, ex.: `S0009` | Identifica a sessão. **Único no mês, em todos os arquivos**, numerado em ordem cronológica. Vazio nos eventos de reserva sem sessão. | **Sim** (agrupar linhas) |
| 6 | `identificacao` | `reserva` \| `rfid` \| `app` | Como o usuário foi liberado: `reserva` = reconhecido pelo horário reservado; `rfid` = cartão no equipamento; `app` = aplicativo. Vazio nos eventos de reserva sem sessão e em sessão não identificada. | **Sim** (sem ela a sessão é "não identificada") |
| 7 | `agendamento_id` | `AG` + 4 dígitos | Id da reserva. Preenchido na linha `Inicio` de sessão **com reserva** e nos eventos `ReservaNaoUtilizada`/`ReservaCancelada`. Vazio = sessão **sem reserva** (avulsa). | **Sim** (taxa sem reserva) |
| 8 | `reserva_inicio` | data/hora | Início da janela reservada. Mesmo preenchimento da coluna 7. | **Sim** (cancelamento tardio, regra de antecedência) |
| 9 | `reserva_fim` | data/hora | Fim da janela reservada. Mesmo preenchimento da coluna 7. | Informativa |
| 10 | `reserva_criada_em` | data/hora | Quando a reserva foi criada no app. Mesmo preenchimento da coluna 7. | **Sim** (validar regra de 1 h) |
| 11 | `energia_acumulada_kwh` | decimal, 3 casas | **Registrador acumulado do medidor** do carregador, em kWh, no instante da linha. Nunca diminui. Vazio nos eventos de reserva. | **Sim** (base do kWh) |
| 12 | `potencia_kw` | decimal, 2 casas | Potência instantânea na tomada, em kW. Vale `0.00` em `Inicio`, `CarroCheio`, `Fim` e nas leituras com o carro parado. | Não (informativa; útil para anomalias) |
| 13 | `soc_pct` | inteiro 0–100 | Nível de bateria informado pelo carro (State of Charge), em %. | Não (informativa; útil para anomalias/IA) |
| 14 | `fila_espera` | `0` ou `1` | `1` = naquele instante **outro usuário** tinha uma reserva ativa (janela `reserva_inicio` ≤ t < `reserva_fim`) e portanto estava esperando o ponto. | **Sim** (ociosidade) |
| 15 | `motivo_parada` | `EVDisconnected` \| `PowerLoss` | Só na linha `Fim`: por que a sessão acabou. `EVDisconnected` = usuário desplugou; `PowerLoss` = queda de energia (sessão interrompida). | **Sim** (interrompida não paga ociosidade) |

**Atenção (energia):** `energia_acumulada_kwh` é energia medida **no medidor** (lado da rede), incluindo perdas do carregador de bordo do carro. É esse valor que se cobra, não a energia que chegou à bateria.

---

## 3. Eventos (coluna `evento`)

| Evento | Quando aparece | Significado |
| --- | --- | --- |
| `Inicio` | uma vez por sessão (primeira linha) | Usuário liberado e carga iniciada. Traz os dados da reserva, se houver. |
| `Medicao` | a cada **15 min**, contados a partir do `Inicio` (não do relógio: ex. 21:18, 21:33, 21:48…) | Leitura periódica do medidor, durante a carga **e** com o carro já carregado e ainda plugado. |
| `CarroCheio` | uma vez, em sessões `EVDisconnected` | O carro parou de puxar energia (limite de carga atingido). Marca o **fim da carga**. Nas leituras seguintes a energia fica constante. |
| `Fim` | uma vez por sessão (última linha) | Sessão encerrada (usuário desplugou ou queda de energia). |
| `ReservaNaoUtilizada` | reserva sem sessão | Reserva em que o usuário não compareceu. `timestamp` = `reserva_inicio` + 30 min. |
| `ReservaCancelada` | reserva cancelada | `timestamp` = momento do cancelamento. |

### Quais colunas cada evento preenche

| Coluna | Inicio | Medicao | CarroCheio | Fim | ReservaNaoUtilizada / ReservaCancelada |
| --- | :-: | :-: | :-: | :-: | :-: |
| timestamp, usuario_id, unidade_id, evento | ✔ | ✔ | ✔ | ✔ | ✔ |
| sessao_id, identificacao | ✔ | ✔ | ✔ | ✔ | — |
| agendamento_id, reserva_inicio/fim/criada_em | ✔ (se houver reserva) | — | — | — | ✔ |
| energia_acumulada_kwh, potencia_kw, soc_pct, fila_espera | ✔ | ✔ | ✔ | ✔ | — |
| motivo_parada | — | — | — | ✔ | — |

---

## 4. Anatomia de uma sessão (exemplo real, semente 5)

Sessão `S0009`, usuária `U03` (carro híbrido, 3,3 kW), com reserva `AG0009`. Linhas resumidas:

```
timestamp            evento      energia   kW    soc  fila
2026-09-09 21:18:00  Inicio      1460.391  0.00  36   0     ← reserva AG0009 (dados na mesma linha)
2026-09-09 21:33:00  Medicao     1461.211  3.25  40   0
   ... leituras a cada 15 min, carga a ~3,25 kW ...
2026-09-10 01:33:00  Medicao     1473.205  1.21  100  0     ← potência cai perto de 100% (curva de carga)
2026-09-10 01:36:00  CarroCheio  1473.264  0.00  100  0     ← fim da carga
2026-09-10 01:48:00  Medicao     1473.264  0.00  100  0     ← energia parada: carro plugado, ocioso
2026-09-10 02:03:00  Medicao     1473.264  0.00  100  1     ← outro usuário na fila a partir daqui
   ... fila_espera = 1 até 05:48 ...
2026-09-10 06:03:00  Medicao     1473.264  0.00  100  0     ← fila acabou
2026-09-10 08:03:00  Fim         1473.264  0.00  100  0     EVDisconnected
```

Derivações:

- **kWh da sessão** = `energia_acumulada_kwh` do `Fim` − do `Inicio` = 1473,264 − 1460,391 = **12,873 kWh**
- **Duração total** = 21:18 → 08:03 = 10 h 45 min (645 min)
- **Fim da carga** = 01:36 (`CarroCheio`)
- **Ociosidade** = 01:36 → 08:03 (6 h 27 min parado), dos quais só importa o tempo com `fila_espera = 1`

---

## 5. Como reconstruir as sessões

1. Ler **todos** os `uso_*.csv` da pasta e juntar as linhas.
2. Linhas com `sessao_id` preenchido → agrupar por `sessao_id` e ordenar por `timestamp`.
3. Linhas `ReservaNaoUtilizada` / `ReservaCancelada` (sem `sessao_id`) → tratar à parte (seção 6.4).
4. Para cada sessão:
   - `inicio` = `timestamp` da linha `Inicio`; `usuario_id`, `identificacao`, `agendamento_id`, `reserva_*` vêm dessa linha.
   - `fim` = `timestamp` da linha `Fim` (se faltar, usar a última linha e registrar aviso).
   - `fim_carga` = `timestamp` do `CarroCheio`. Se não houver (sessão `PowerLoss`), `fim_carga = fim`.
   - `kWh` = energia do `Fim` − energia do `Inicio`.

---

## 6. Regras de cobrança

Valores de tarifa e taxas são **arbitrários** (item "definição arbitrária dos valores" do plano da Sprint 2). Devem ficar **parametrizados**, não fixos no código.

### Parâmetros padrão

| Parâmetro | Valor | Observação |
| --- | --- | --- |
| Tarifa fora de ponta | R$ 0,85/kWh | |
| Tarifa intermediária | R$ 1,20/kWh | horas cheias 17 e 21 (dias úteis) |
| Tarifa de ponta | R$ 1,70/kWh | horas cheias 18, 19 e 20 (dias úteis) |
| Fim de semana e feriados | fora de ponta o dia todo | feriados nacionais 2026 (ver `calcular_fatura.py`) |
| Antecedência mínima da reserva | 60 min | regra de negócio: reserva só até 1 h antes |
| Carência de ociosidade | 15 min | tempo grátis após o fim da carga |
| Bloco de ociosidade | 30 min | cada bloco **iniciado** é cobrado |
| Taxa por bloco de ociosidade | R$ 2,00 | |
| Teto de ociosidade por sessão | R$ 20,00 | |
| Taxa de sessão sem reserva | R$ 1,50 | |
| Taxa de reserva não utilizada | R$ 5,00 | |
| Custo fixo mensal por unidade | R$ 15,00 | cobrado usando ou não o carregador |

### 6.1 Energia (por faixa horária)

Para cada par de leituras consecutivas da sessão `(t0, e0)` e `(t1, e1)`:

```
kwh_intervalo = e1 - e0
faixa         = faixa do ponto médio  t0 + (t1 - t0)/2
custo        += kwh_intervalo * tarifa[faixa]
```

A faixa é definida pelo **ponto médio do intervalo** (aproximação das leituras de 15 min). Dia útil = segunda a sexta que não seja feriado.

### 6.2 Ociosidade (carro plugado já carregado, com outra pessoa esperando)

```
inicio_ocio = fim_carga + carência (15 min)
espera      = soma dos minutos, entre inicio_ocio e o Fim, dos intervalos de leitura
              cuja linha final tem fila_espera = 1
blocos      = ceil(espera / 30 min)
custo       = min(blocos * R$ 2,00, R$ 20,00)
```

Só cobra se **outro usuário estava na fila** (`fila_espera = 1`); carro ocioso sem ninguém esperando é grátis. **Não se aplica** a sessões com `motivo_parada = PowerLoss`.

### 6.3 Sessão sem reserva

Se `agendamento_id` está **vazio** na linha `Inicio`: soma R$ 1,50 (taxa de sessão avulsa).

### 6.4 Reserva não utilizada

- `ReservaNaoUtilizada` → cobra R$ 5,00 do `usuario_id`.
- `ReservaCancelada` → cobra R$ 5,00 **somente se** `timestamp` do cancelamento > `reserva_inicio` − 60 min (cancelamento tardio). Cancelar com mais de 1 h de antecedência é grátis.

### 6.5 Custo fixo

R$ 15,00 por unidade cadastrada, cobrado de todos os usuários presentes nos arquivos, mesmo sem sessão.

### 6.6 Sessão não identificada

Se `usuario_id` vazio (ou inexistente) ou `identificacao` vazia: **não é cobrada de ninguém**. Vai para um grupo `NAO_IDENTIFICADO` (energia na tarifa normal, sem taxas) e gera aviso para o gestor investigar. O carregador só deveria liberar com identificação, então isso indica falha de registro, não uso indevido.

### Total do usuário no mês

```
total = energia + ociosidade + taxa_sem_reserva + no_show + custo_fixo
```

---

## 7. Exemplo calculado (sessão S0009 acima)

| Componente | Cálculo | Valor |
| --- | --- | --- |
| Energia, faixa intermediária (21h) | 2,457 kWh × R$ 1,20 | R$ 2,95 |
| Energia, faixa fora de ponta | 10,416 kWh × R$ 0,85 | R$ 8,85 |
| **Subtotal energia** | | **R$ 11,80** |
| Ociosidade | fim da carga 01:36 → fora da carência a partir de 01:51; fila de 02:03 a 05:48 (+12 min do primeiro intervalo) = **237 min** → ⌈237/30⌉ = 8 blocos × R$ 2,00 | **R$ 16,00** |
| Sem reserva | tinha reserva (AG0009) | R$ 0,00 |
| **Total da sessão** | | **R$ 27,80** |

---

## 8. Validações recomendadas (geram aviso, não interrompem o cálculo)

| Verificação | Por quê |
| --- | --- |
| Reserva criada com menos de 60 min de antecedência (`reserva_criada_em` > `reserva_inicio` − 60 min) | Viola a regra do app. A reserva é honrada, mas deve ser sinalizada. |
| Sessão sem `usuario_id`/`identificacao` | Vai para `NAO_IDENTIFICADO` (seção 6.6). |
| Início do registrador de uma sessão ≠ fim da sessão anterior (considerando todos os usuários) | Consumo fora de sessão: energia usada sem registro. Ex.: "medidor avançou 3,2 kWh". |
| Sessões sobrepostas no tempo | Só há um ponto de recarga. |
| Energia acumulada diminuindo entre leituras | Medidor com defeito ou dado corrompido. |
| Sessão sem `Fim` ou sem `CarroCheio` (e sem `PowerLoss`) | Dado incompleto; usar a última leitura e avisar. |
| `sessao_id` com usuários diferentes | Dado inconsistente. |
| Conciliação final: (último registrador − primeiro) ≠ soma dos kWh das sessões | Indica energia sem sessão ou arquivos faltando. |

**Importante:** a verificação de continuidade do medidor só funciona com **todos os arquivos** carregados. Se faltar o arquivo de um usuário, aparecerão avisos de "consumo fora de sessão", o que é esperado.

---

## 9. Garantias dos dados gerados (invariantes)

- Só há **uma sessão por vez** (um ponto de recarga); sessões de todos os usuários nunca se sobrepõem no tempo.
- O registrador do medidor é **contínuo**: a primeira leitura de cada sessão é igual à última da sessão anterior (de qualquer usuário), exceto na anomalia injetada.
- `energia_acumulada_kwh` nunca diminui; fica constante com o carro parado.
- Reservas não canceladas **não se sobrepõem** entre si.
- Uma sessão avulsa não começa dentro da janela reservada de outro usuário, mas **pode ficar plugada** depois do fim da carga até invadir a reserva de outro (é o que `fila_espera = 1` captura).
- Uma sessão com reserva pode começar **depois** de `reserva_inicio` (atraso do usuário ou carro anterior ainda plugado).
- Potência nunca excede o limite do carro (6,6 kW nos modelos BYD e 3,3 kW no híbrido) nem o do carregador (7 kW). A potência cai perto de 100% de bateria (curva de carga em AC, hipótese do gerador).
- Dados normais de uso: por usuário, de 2 a 20 sessões e de 40 a 380 kWh no mês; no ponto de recarga, de 400 a 1.300 kWh.

---

## 10. Dados de referência para testar o seu script

Gerando com a mesma versão do gerador e a **semente 5**:

```
python gerar_uso_carregador.py --seed 5 --saida ref5
```

o resultado esperado da fatura (34 sessões, 774 kWh, **0 avisos**) é:

| Unidade | Usuário | Sessões | kWh | Energia | Ociosidade | Sem reserva | No-show | Fixo | **Total** |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A-11 | Ana Beatriz Souza | 7 | 154,47 | 159,06 | 0,00 | 1,50 | 0,00 | 15,00 | **175,56** |
| B-14 | Ricardo Mendes | 6 | 277,66 | 269,56 | 0,00 | 6,00 | 0,00 | 15,00 | **290,56** |
| B-21 | Juliana Castro | 11 | 129,99 | 140,10 | 22,00 | 10,50 | 0,00 | 15,00 | **187,60** |
| B-33 | Marcos Vinícius Rocha | 6 | 110,36 | 101,67 | 0,00 | 6,00 | 5,00 | 15,00 | **127,67** |
| B-42 | Patrícia Nogueira | 4 | 101,54 | 86,31 | 0,00 | 1,50 | 0,00 | 15,00 | **102,81** |
| | **Total a arrecadar** | | | | | | | | **R$ 884,19** |

Casos úteis dentro dessa mesma base: sessão `S0009` (ociosidade de R$ 16,00, exemplo da seção 7), sessão `S0020` (ociosidade de R$ 6,00, 85 min com fila) e a reserva `AG0004` do usuário U04 (no-show de R$ 5,00).

Para testar as validações, gere dados com problemas injetados:

```
python gerar_uso_carregador.py --anomalias
```

Isso cria: uma reserva criada 20 min antes (viola a regra de 1 h), uma sessão sem usuário (arquivo `uso_NAO_IDENTIFICADO.csv`) e um salto de 3,2 kWh no medidor entre duas sessões.

> Sem `--seed`, cada execução gera dados **diferentes** (sempre dentro de faixas normais de uso) e imprime a semente usada, que pode ser reaproveitada para repetir o mesmo conjunto.

---

## 11. Premissas e pontos em aberto

- **Valores de tarifa e taxas são arbitrários**: o grupo/condomínio deve definir os definitivos.
- **`fila_espera`** foi modelado como um campo registrado pela plataforma (cruza reservas com o momento da leitura). Se o carregador real não fornecer isso, a ociosidade deve ser derivada cruzando as janelas de reserva dos demais usuários.
- **`soc_pct`** assume que o carro informa o nível de bateria (ex.: via ISO 15118 ou app). Não influencia a cobrança.
- **Curva de potência perto de 100%** e **perdas de 10% do carregador de bordo** são hipóteses do gerador, não medições.
- **Leituras a cada 15 min**: a faixa horária é decidida pelo ponto médio de cada intervalo (aproximação). Se o carregador real tiver leituras mais frequentes, o erro diminui.
- O arquivo real do SEMS+/GoodWe pode ter nomes de colunas diferentes; se for o caso, basta mapear para as colunas desta especificação.
