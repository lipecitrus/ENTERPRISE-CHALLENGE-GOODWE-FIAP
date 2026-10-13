# EV ChargeOps — Interface de terminal (`main.py`)

Programa de terminal para o carregador compartilhado do condomínio: cadastro com CPF, agendamento, liberação do carregador, painel do gestor e fatura mensal. Os dados do app ficam em um arquivo Excel (`.xlsx`) lido e gravado com pandas. A fatura é calculada pelo código do repositório (`src/rateio`).

## Requisitos

- Python 3.10 ou superior
- pandas e openpyxl:

```
pip install pandas openpyxl
```

## Como rodar

Na raiz do repositório:

```
python gerar_uso_carregador.py --seed 5     # gera a pasta uso_carregador (dados fictícios)
python main.py
```

A pasta `uso_carregador` precisa existir para a fatura funcionar. Sem ela, o programa avisa e sugere o comando acima.

## Menus

**Tela inicial:** Entrar (CPF e senha), Cadastrar-se e Painel do gestor.

**Morador (depois do login):**

| Opção | O que faz |
| --- | --- |
| Novo agendamento | Reserva o ponto de recarga em blocos de 30 minutos. |
| Meus agendamentos | Lista as últimas reservas e permite cancelar. |
| Iniciar carregamento | Libera o carregador, com reserva ou avulso, e grava quem iniciou. |
| Encerrar carregamento | Registra o fim do carregamento. |
| Fatura mensal | Mostra a fatura do morador, calculada com os dados do medidor. |

**Gestor:** resumo do mês (total a arrecadar), liberações (quem iniciou cada carregamento), agenda de reservas e exportação da fatura em `.xlsx`.

## Regras

Os valores vêm de `config/parametros_rateio.csv` (lido por `carregar_parametros()`), sem números fixos no código.

- **Agendamento:** início em hora cheia ou meia hora, duração em múltiplos de 30 minutos, antecedência mínima de 60 minutos e sem sobreposição com outra reserva ativa.
- **Uso com reserva:** o carregador só é liberado para quem tem reserva ativa naquele horário, com tolerância de 30 minutos antes do início.
- **Uso avulso:** permitido quando o ponto está livre e não há reserva de outro usuário em andamento. Taxa de R$ 1,50 por sessão. A identificação é por app ou RFID.
- **Reserva não utilizada:** a reserva ativa que não teve liberação até 30 minutos depois do início passa a `nao_utilizado`. Taxa de R$ 5,00.
- **Cancelamento tardio:** cancelar com menos de 60 minutos do início gera taxa de R$ 5,00. O programa avisa e pede confirmação antes de cancelar.
- **Cadastro:** CPF validado pelos dígitos verificadores e senha de no mínimo 6 caracteres.
  - Se a unidade já aparece nos arquivos de uso, o cadastro reaproveita o código do usuário (por exemplo `U03`) e a fatura fica ligada ao CPF.
  - Cada unidade tem um único cadastro.
- **Segurança:**
  - Senhas (do morador e do gestor) são guardadas com hash PBKDF2, nunca em texto.
  - O CPF é guardado só com os 11 dígitos e aparece mascarado na tela (`***.982.247-**`).
  - A senha do gestor é definida no primeiro acesso ao painel.

## Arquivos

| Arquivo | Descrição |
| --- | --- |
| `ev_chargeops.xlsx` | Dados do app, criado na primeira gravação (primeiro cadastro). |
| `fatura_saida/fatura_mensal.xlsx` | Exportação do gestor, com as abas `faturas` e `detalhe`. |
| `uso_carregador/` | CSVs de uso do medidor (gerados por `gerar_uso_carregador.py`). |

Abas do `ev_chargeops.xlsx`:

| Aba | Colunas |
| --- | --- |
| `usuarios` | cpf, usuario_id, nome, unidade_id, senha |
| `agendamentos` | id, usuario_id, inicio, fim, status, tardio |
| `liberacoes` | id, usuario_id, unidade_id, identificacao, agendamento_id, inicio, fim |
| `config` | chave, valor (senha do gestor) |

Status de um agendamento: `ativo`, `utilizado`, `cancelado` ou `nao_utilizado`. Em `liberacoes`, `agendamento_id` vazio significa uso avulso.

## Uso dos arquivos do repositório

| Do repositório | Usado para |
| --- | --- |
| `config/parametros_rateio.csv` | Antecedência, tolerância e taxas. |
| `leitor_uso.py` e `src/rateio` (`calcular_da_pasta`) | Leitura dos CSVs de uso e cálculo das faturas. |
| `src/rateio/saida.py` (`resumo`, `brl`) | Tabela do gestor e formatação de valores. |

## Para testar

CPFs válidos de exemplo: `529.982.247-25` e `111.444.777-35`.

1. Gere os dados de uso com a semente 5 e rode `python main.py`.
2. Cadastre-se com a unidade `B-21` (corresponde à Juliana Castro nos dados de exemplo).
3. Entre e abra **Fatura mensal**. Com a semente 5, o total esperado é R$ 187,60.
4. Crie uma reserva para daqui a mais de 1 hora e tente repetir o mesmo horário: a segunda tentativa deve ser recusada.
5. Em **Iniciar carregamento**, libere o carregador e confira a liberação no painel do gestor.

## Limitações

- O rateio lê só os CSVs do medidor. Reservas e liberações do app não entram no valor da fatura. As taxas de reserva não utilizada, de cancelamento tardio e de uso avulso registradas no app aparecem apenas como aviso na tela.
- O arquivo `ev_chargeops.xlsx` não pode estar aberto no Excel enquanto o programa roda, porque o Windows bloqueia a gravação.
- Dados em Excel servem para protótipo e uso com poucos usuários. Para vários acessos ao mesmo tempo, o ideal é um banco de dados.
- Todos os dados são fictícios.
