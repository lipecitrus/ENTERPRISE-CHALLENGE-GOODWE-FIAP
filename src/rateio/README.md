# Frente 2 — Rateio e fatura

Cálculo da fatura mensal por usuário (seção 3 do *Sistema de Leitura v4*), sobre os objetos
entregues pelo leitor da frente 1 (`leitor_uso.py`). O `calcular_fatura.py` da raiz é só a linha de
comando; todo o cálculo está aqui.

| Arquivo | O que faz |
| --- | --- |
| `config/parametros_rateio.csv` | Tarifas e taxas (seção 3.1). Nada de valor fixo no código. Um `parametros_rateio.csv` na pasta de uso sobrescreve só o que trouxer. |
| `parametros.py` | Lê e valida os parâmetros (`Parametros`, `carregar_parametros`). |
| `regras.py` | Uma função por regra: faixa horária, energia pelo ponto médio, ociosidade com fila, taxa sem reserva, no-show, sessão não identificada. |
| `validacoes.py` | Avisos da seção 5.1 que precisam de todas as sessões ou dos parâmetros (antecedência, continuidade do medidor, sobreposição, conciliação). Os demais já ficam no leitor. |
| `fatura.py` | `calcular_rateio` → `ResultadoRateio` com `Fatura` (por usuário e competência `AAAA-MM`) e `CobrancaSessao` (detalhe). São os objetos para a frente 3. |
| `saida.py` | `fatura_mensal.csv`, `detalhe_sessoes.csv`, `avisos.txt` (separador `;`, decimal `,`). |
| `contrato.py` | Único ponto que importa o leitor; quando ele for para `src/ingestao`, nada mais muda. |

## Como rodar (na raiz do repositório)

```
python gerar_uso_carregador.py --seed 5
python calcular_fatura.py                  # padrões: uso_carregador -> fatura_saida
python calcular_fatura.py <pasta_uso> <pasta_saida>   # (ou: python -m src.rateio ...)
python -m unittest discover -s tests -v
```

Em código:

```python
from src.rateio import calcular_da_pasta
r = calcular_da_pasta("uso_carregador")
r.total_arrecadar, r.fatura("U03").total, r.cobranca("S0009").ociosidade
```

## Testes (`tests/test_rateio.py`)

- Regras isoladas com sessões montadas à mão.
- Aceitação da semente 5: 34 sessões, 774 kWh, 0 avisos, **R$ 884,20**, tabela por usuário,
  S0009 (R$ 27,80; 237 min → 8 blocos), S0020 (85 min → R$ 6,00), no-show AG0004.
- `--anomalias`: os 3 problemas injetados geram aviso; a sessão sem usuário vai para `NAO_IDENTIFICADO`.
- Propriedades em outras sementes, outro mês e com anomalias (toda sessão cobrada uma única vez,
  kWh conferem, total = soma dos componentes, teto de ociosidade respeitado).
- Linha de comando `calcular_fatura.py` de ponta a ponta.

## Arredondamento e competência

- **Centavos:** cada cobrança (energia, ociosidade e taxas de uma sessão, no-show) é arredondada a
  centavos, meio para cima, no momento em que é criada; a fatura só soma valores já arredondados.
  Assim as linhas do detalhe fecham exatamente com o total que o morador vê.
  Consequência: a semente 5 dá **R$ 884,20**, e não os R$ 884,19 da seção 3.3 do documento (que
  somava sem arredondar por sessão): Ana Beatriz R$ 175,57 (energia 159,07) e Patrícia R$ 102,80
  (energia 86,30); os demais usuários não mudam. O documento precisa ser atualizado.
- **Competência:** `Fatura.competencia` e `ResultadoRateio.competencia` (`AAAA-MM`), também na
  1ª coluna de `fatura_mensal.csv`. É o mês do início das sessões e reservas (sessão que vira o mês
  conta no mês em que começou). Dados de mais de um mês geram aviso. Pode ser informada:
  `calcular_da_pasta(pasta, competencia="2026-09")`.

## Em relação ao `calcular_fatura.py` de exemplo

O exemplo enviado com o documento foi substituído por esta implementação (os valores da seção 3.3
batem, exceto o centavo explicado acima). Mudanças: parâmetros saem do código para `config/`; regras em funções
separadas e testadas; o detalhe sai em ordem cronológica (no-shows junto das sessões); a sessão
não identificada traz o motivo na observação; o aviso de energia diminuindo não é repetido (o
leitor já o emite); cancelamento sem `reserva_inicio` não derruba o cálculo; no-show de usuário
desconhecido gera aviso.
