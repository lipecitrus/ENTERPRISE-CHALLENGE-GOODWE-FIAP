# ENTERPRISE CHALLENGE 2026 — GOODWE + FIAP

Grupo 11: Filipe Augusto Chaves (), Yury Alexander Tavares (), Murillo Gomes de Almeida (rm572196), Arthur Henrique Ruiz Ramos ()

## DESCRIÇÃO DO PROBLEMA E DO CONTEXTO DO DESAFIO

### Contexto

A GoodWe, fabricante global de inversores e sistemas de armazenamento de energia (presença em mais de 100 países, 100GW+ de capacidade instalada).

O cenário de fundo é o crescimento acelerado da frota de veículos elétricos, que está pressionando infraestruturas de recarga compartilhadas — condomínios residenciais, edifícios corporativos e campus universitários — a lidar com múltiplos usuários disputando um número limitado de pontos de carga.

### O Problema Central

Essas infraestruturas compartilhadas não possuem mecanismos integrados para:

- Estruturar sessões por usuário — não há um registro organizado de quem carregou, quando e por quanto tempo.
- Calcular consumo individual — falta apuração precisa de quantos kWh cada usuário efetivamente consumiu.
- Aplicar regras de rateio justas — sem dados estruturados, a divisão de custos de energia entre moradores/usuários tende a ser genérica ou arbitrária, gerando potenciais conflitos.
- Oferecer uma experiência digital clara — tanto para o usuário final (morador) quanto para o gestor (condomínio, empresa, campus), falta uma interface que traduza os dados em informação compreensível.

Ou seja, o problema não é técnico no sentido de "o carregador não funciona", é um problema de gestão de dados e governança de uso compartilhado de um recurso físico.

### Oportunidade

Cada sessão de recarga já gera dados ricos e mensuráveis:

- Duração da sessão
- Volume de energia entregue (kWh)
- Horário de uso
- Frequência de utilização
- Picos de demanda
- Intervalos de ociosidade do equipamento

O texto aponta que esses dados, hoje provavelmente subutilizados ou dispersos, podem se transformar em inteligência operacional quando organizados, processados e analisados de forma estruturada.

### Proposta de Solução

Surge como resposta a esse problema, propondo usar inteligência artificial como motor lógico para:

- Transformar dados brutos de sessões de recarga em informação útil;
- Automatizar o cálculo de consumo individual;
- Viabilizar rateios mais justos e transparentes;
- Entregar uma camada digital de gestão e visualização tanto para usuários quanto para administradores da infraestrutura.

## RESULTADO DAS TRÊS FRENTES DE PESQUISA

### FRENTE 1

**O que são infraestruturas de recarga compartilhada e quais são os principais desafios operacionais enfrentados por gestores de condomínios, edifícios corporativos ou campus universitários?**

As infraestruturas de recarga compartilhada são estações destinada ao carregamento de veículos elétricos projetadas para serem utilizadas por múltiplos usuários ou moradores. Dentro de instalações como empresas, condomínios, moradias ou universidades, há a estação física, concedendo a recarga da bateria do veículo. Estas estações possuem, por sua vez, um sistema de gerenciamento inteligente na qual atua na distribuição de energia de maneira consciente entre os dispositivos e métodos de cobrança por consumo.

Apesar da implementação nos espaços públicos, é possível identificar a existência de problemas relacionados a distribuição energética das estações perante seus dispositivos. A instalação de várias unidades físicas de carregadores para o usuário pode exigir uma alta demanda elétrica, especialmente em horários de maior necessidade de utilização. Sem a gestão deste item, o sistema elétrico do edifício pode sobrecarregar e gerar um colapso na rede de energia.

Outro desafio enfrentado perante a infraestrutura de recarga compartilhada diz respeito às políticas internas e regras operacionais das instituições possuidoras das estações. É necessária uma administração relacionada aos acessos, reservas, tempo de permanência, prioridade de carregamento e liberação dos dispositivos após o uso para outrem. A ausência destas regras pode gerar frustração e conflitos ao usuário.

A confiabilidade dos dispositivos é trivial diante a operação do dispositivo já que os equipamentos estão sujeitos a falhas elétricas, comunicativas, deterioração física e interrupção da rede. Desta forma, é necessário a implementação de estratégias  relacionadas  a  manutenção  como  a  manutenção  preventiva, monitoramento remoto das estações, sistemas inteligentes capazes de indicarem desempenho e taxa mo s de falhas.

Além dos aspectos técnicos, existe o desafio relacionado ao modelo de gestão econômica da infraestrutura. O administrador deve definir como os custos de energia, manutenção e operação serão distribuídos entre os usuários, considerando alternativas como cobrança individual, assinatura, rateio coletivo ou fornecimento gratuito.

Há a exigência normativa relacionada ao projeto de instalação dos equipamentos, de forma que se exige projetos elétricos - desenho técnico que define cálculos de dimensões, medições específicas, materiais necessários para execução da atividade, para a implementação física do dispositivo -, projeto executivo – documentos relacionados entre condomínio e/ou moradia e concessionária de energia.

Além dos desafios técnicos e operacionais, existe, por fim, o problema referente a gestão econômica relacionada a cobrança após a utilização da recarga no veículo elétrico. A administração deve definir como os custos de utilização do dispositivo - tempo, intensidade de energia utilizada etc. - manutenção preventiva, a energia fornecida pela concessionária e operação serão distribuídos aos consumidores, considerando modelos de cobrança individuais.

**Como funciona uma sessão de recarga do ponto de vista técnico: o que acontece entre o momento em que o veículo é conectado e o encerramento da sessão, quais dados são gerados e como podem ser capturados;**

Em uma sessão de recarga de um veículo elétrico, há uma série de dados compartilhados entre o veículo elétrico para o carregado e sistema de gestão em nuvem. Esta atividade ocorre por meio de dois padrões técnicos operacionais: a comunicação entre o veículo e o carregador físico - padrão normativo ISO 15118 – e a intercomunicação entre carregador e servidores externos - padrão OCPP (Protocolo de Ponto de Carga Aberto). Após a conexão física entre o carregador e o veículo elétrico, inicia-se uma comunicação contínua entre: VE – Unidade de Recarga Elétrica – Servidor Externo (gerenciamento).

O processo inicia quando o usuário conecta o cabo de carregamento ao veículo e ao equipamento de recarga. O carregador realiza uma verificação inicial da conexão elétrica e estabelece comunicação com o sistema eletrônico do veículo.

Neste estágio, são analisados parâmetros para autenticação e autorização para início da recarga. De um lado, o usuário pode realizar a liberação através de uma tag RFID, aplicativo externo correspondente ao carregador, leitura via QR Code ou cadastro interno no sistema do edifício. Em seguida, feita a liberação, começa-se o processo de recarga do veículo elétrico.

Durante o processo de recarga, devido a conexão estabelecida, ocorre o processo de gerenciamento inteligente (Smart Charging) das variáveis elétricas e operacionais apresentadas pelo veículo, como nível atual da bateria, tempo limite de partida, duração da sessão, temperatura dos componentes, potência e corrente fornecidas, condições de segurança e comunicação entre sistemas. A estação analisa essas informações com base nos limites da rede local, prioridades tarifárias e converte a energia (de Corrente Alternada - CA para Corrente Contínua - CC, se for um carregador rápido)

Quando finalizado o processo (seja por carregamento 100% concluído ou por interrupção externa – falha do equipamento ou interrupção manual.), ocorre o registro detalhado da atividade da recarga, contendo:

- Identificação do usuário;
- Identificação do carregador utilizado;
- Data e horário de início;
- Data e horário de término;
- Duração total da sessão;
- Energia consumida em kWh;
- Potência média e máxima utilizada;
- Custo associado à recarga;
- Eventos de falha ou interrupção.

A coleta destes dados é essencial, tendo em vista que contém todo o histórico da recarga, facilitando a gestão operacional, técnica e financeira dentro da instalação fornecedora do serviço.

**Quais modelos de negócio existem para recarga compartilhada no Brasil e no mundo: recarga gratuita, cobrança por kWh, cobrança por tempo, assinatura mensal ou rateio condominial.**

O modelo de negócio referente ao sistema de recarga compartilhada baseia-se na utilização e monetização da infraestrutura, contando com fatores de cobrança dentro dos espaços que fornecem o serviço ao consumidor. Portanto, existem modelos de precificação relacionados a operação do equipamento.

**Modelo de Recarga Gratuita (Subsidiado):**
Esta aplicação concede ao consumidor o serviço de recarga do veículo elétrico sem a cobrança e/ou precificação pela utilização. Este modelo é utilizado por espaços como shoppings, hotéis, universidade e condomínio. Os custos perante manutenção, energia concedida e operação são de responsabilidade da organização e/ou parceria comercial do empreendimento.

**Modelo de Cobrança por Energia Consumida (R$/kWh):**
Neste modelo a precificação está diretamente relacionada ao consumo de energia elétrica utilizada na operação de recarga.

**Modelo de Utilização por Tempo (R$/Hrs):**
Neste modelo, monetiza-se o tempo de consumo do serviço, independente da intensidade de energia durante a sessão.

**Modelo de Cobrança por Plano:**
O consumidor filiado ao espaço que fornece o serviço de recarga compartilhada tem o desconto de um valor fixo, já que possuem este vínculo através de um plano ou franquia (para veículos elétricos em frota). Desta forma, ocorre a previsibilidade de custo por operação para o usuário.

**Modelo de Rateio Condominial:**
Perante a prestação do sistema de carregamento compartilhado pelo condomínio residencial, é possível que a gestão financeira utilize o rateio na precificação da atividade do equipamento através de softwares de controle de consumo dos moradores e consumidores do serviço. Ademais, é possível que ocorra a cobrança individualizada do consumo, garantindo maior transparência perante os procedimentos de cobrança.

**Opção de Aprofundamento C — Análise de dados públicos: pesquise e análise dados sobre o crescimento da frota de veículos elétricos no Brasil, distribuição de pontos de recarga e perfis de uso.**

Segundo o site Monitor Mercantil, venda de carros eletrificados dispara e cresce 65,5% em 2026. O segmento de híbridos e elétricos alcança 15,9% de participação. Com um crescimento expressivo de 65,5% nos dois primeiros meses de 2026, o segmento de veículos eletrificados atingiu a marca de 55.961 unidades emplacadas no Brasil. O balanço, divulgado pela Associação Nacional dos Fabricantes de Veículos Automotores (Anfavea), confirma que a eletromobilidade deixou de ser uma tendência de nicho para se tornar o motor de crescimento do mercado brasileiro.

O site Smabc nos traz a informação de que Brasil chega a 25 mil eletropostos, sendo 33% de carga rápida. A infraestrutura de recarga para veículos elétricos cresceu pouco mais de 20% em três meses. O país alcançou 25.455 pontos públicos e semipúblicos de recarga em maio de 2026, crescimento de 20,9% em relação a fevereiro — data do último levantamento —, quando a rede contava com 21.060 equipamentos.

O principal destaque do levantamento divulgado pela Tupi, plataforma de mobilidade elétrica, em parceria com a Associação Brasileira do Veículo Elétrico (ABVE), foi o avanço da recarga rápida. Em apenas três meses, o número de carregadores DC passou de 6.479 para 8.606 unidades, crescimento de 32,8%. Com isso, a participação da recarga rápida na infraestrutura nacional aumentou de 30,8% para 33,8%.

Já os carregadores lentos (AC) cresceram 15,5% no período, passando de 14.582 para 16.836 equipamentos. Segundo a ABVE e a Tupi, o resultado mostra que o mercado brasileiro entrou em uma nova fase de expansão da infraestrutura, impulsionada tanto pela ampliação dos eletropostos quanto pelo avanço dos carregadores ultrarrápidos.

Outro dado que chamou atenção no levantamento foi a retomada do crescimento dos carregadores lentos (AC). De acordo com a ABVE e a Tupi, a reação coincide com a entrada em vigor da Lei 18.403/2026, sancionada em São Paulo, que garante aos moradores o direito de instalar carregadores em vagas privativas de condomínios. Outros estados também consolidaram normativas sobre o tema na sequência, e ampliaram a discussão para todo o território nacional.

Os usuários desse tipo de veículo são associados normalmente a perfis de consumo de conectividade, tecnologia e inovação, além de terem uma relação com a busca por sustentabilidade e maneiras alternativas de mobilidade. O entusiasmo para a utilização de veículos elétricos cresceu significantemente no ambiente dos motoristas de aplicativo, fator este apresentado devido a redução do custo de reabastecimento e a menor necessidade de reparos mecânicos.

Além disso, estes veículos apresentam redução de emissão dos gases poluentes, trazendo uma alternativa mais sustentável para o cotidiano. Por fim, é notável a predominância da utilização dos veículos elétricos no centro urbano, já que traz ao consumidor a mais atual tecnologia, desde o próprio carro em si, até as estações de recarga compartilhada que crescem fortemente no Brasil, apresentando uma gestão mais inteligente de energia, operação e sustentabilidade.

### FRENTE 2

**Resolução Normativa ANEEL nº 1000 (e suas alterações subsequentes)**

**Objeto e Abrangência**
Regula os direitos e deveres de consumidores e distribuidoras de energia elétrica, aplicando-se a concessionárias, permissionárias e todos os usuários do sistema de distribuição.

**Conexão ao Sistema**
- A conexão é um direito do consumidor, podendo ser permanente ou temporária.
- A distribuidora é obrigada a fornecer orçamentos gratuitos e realizar obras nos prazos regulamentados.
- Conexões até 50 kW em baixa tensão são gratuitas para consumidores de baixa renda.
- Há regras específicas para microgeração e minigeração distribuída (painéis solares, etc.).

**Contratos**
- Grupo B (baixa tensão): contrato de adesão por prazo indeterminado.
- Grupo A (alta tensão): CUSD e CCER com vigência de 12 meses, prorrogáveis automaticamente.
- Consumidores do Grupo A podem migrar para o Mercado Livre (ACL).

**Tarifas e Benefícios**
- Tarifa Social (TSEE): para famílias inscritas no CadÚnico com renda de até meio salário mínimo per capita, com descontos progressivos no consumo.
- Residencial Desconto Social: para famílias com renda entre meio e um salário mínimo per capita.
- Classes tarifárias: residencial, industrial, comercial, rural, poder público, iluminação pública, serviço público e consumo próprio.
- Benefícios para irrigação e aquicultura com reduções de até 90% nas tarifas.

**Faturamento e Pagamento**
- Leitura mensal obrigatória com ciclo de 27 a 33 dias.
- Fatura deve conter todas as informações detalhadas de consumo, tarifas e tributos.
- Vencimento mínimo de 5 dias úteis após apresentação da fatura.
- Erros de faturamento a maior geram devolução em dobro corrigida pelo IPCA.

**Suspensão e Religação**
- Suspensão por inadimplemento exige notificação prévia de 15 dias.
- Consumidores de baixa renda têm prazo mínimo de 30 dias entre vencimento e suspensão.
- Religação em caso de suspensão indevida deve ocorrer em 4 horas.
- Suspensão vedada às sextas, sábados, domingos, vésperas e feriados.

**Microgeração e Minigeração Distribuída (SCEE)**
- Sistema de Compensação de Energia Elétrica permite que excedentes gerados (ex.: solar) sejam compensados na fatura.
- Créditos de energia têm validade de 60 meses.
- Regras de transição até 2045 para quem instalou painéis antes de janeiro de 2022.
- Minigeradores acima de 500 kW devem apresentar garantia de fiel cumprimento.

**Qualidade do Serviço**
- Indicadores de continuidade (frequência e duração de interrupções) com limites regulados.
- Descumprimento de prazos gera compensação financeira automática ao consumidor.
- Distribuidora deve avisar interrupções programadas com antecedência mínima de 72 horas (até 5 dias para consumidores especiais).

**Atendimento ao Consumidor**
- Canais obrigatórios: presencial, telefônico 24h, internet e plataforma Consumidor.gov.br.
- Reclamações devem ser resolvidas em até 5 dias úteis (ou 10 dias com visita técnica).
- Tempo de espera no atendimento presencial: máximo 30 minutos.
- Concessionárias com mais de 60.000 consumidores devem ter Ouvidoria própria.

**Ressarcimento de Danos Elétricos**
- Aplica-se exclusivamente ao Grupo B (baixa tensão).
- Prazo para solicitar ressarcimento: 5 anos da ocorrência.
- Distribuidora deve responder em 15 a 30 dias e ressarcir em até 20 dias após o deferimento.
- Responsabilidade objetiva da distribuidora (independe de dolo ou culpa).

**Iluminação Pública**
- Responsabilidade de operação e manutenção é do poder público municipal.
- Distribuidora realiza a medição e faturamento dos pontos de iluminação.
- Arrecadação da CIP (Contribuição de Iluminação Pública) é feita pela distribuidora na fatura.

### FRENTE 3

**Quais são as camadas da plataforma EV ChargeOps**

**Camada física**
- EV Charger: linha HCA G2
- Medidores (MODBUS): esses medidores são muito usados na indústria, pois é relativamente fácil de se implantar em sistemas, além de não ser necessário pagar taxas de licença por cada uso.
- Controladores (OCPP): O protocolo de Ponto de Carregamento é um sistema central de gerenciamento de estações de recarga para veículos elétricos. O OCPP permite uma comunicação fluida entre carregadores e plataformas de gerenciamento, dessa forma é possível centralizar o monitoramento e o controle de carga.

**Conectividade**

Uso de tecnologias para se conectar ao carregador e, assim, acessar o usuário:

1. RFID, tecnologia usada para identificar dados por meio de aproximação (bom para identificar o usuário que usará o posto de recarga)
2. LAN, rede de área local é utilizado para troca rápida de informações entre computadores em um ambiente, pode ser por meio da tecnologia ethernet ou wi-fi (bom para troca de dados entre o posto de recarga e o servidor)
3. Bluetooth, tecnologia usada para ligar aparelhos por meio de ondas de rádio de curto alcance (bom para fazer a ligação entre o dispositivo do usuário com o posto de recarga)
4. API SEMS, esta API permite a interação do usuário com o posto de carregamento, assim se torna possível ter a leitura dos eventos ocorridos durante uma sessão de recarga.

**Aplicação**
- Banco de dados com os usuários cadastrados e informações ligadas a eles. Além de unidades de recarga, sessões e faturas.
- Coleta de dados dos eventos obtidos, por meio do controlador OCPP. Utilização dos dados coletados para lançar no perfil do usuário para receber a fatura referente ao uso do carregador.
- IA na previsão de anomalias e de uso

**Apresentação**
- Interface gráfica amigável para usuários e gestores. Aqui será possível consultar o uso e as faturas de cada usuário

**Como os dados fluem da sessão de recarga até a fatura do usuário**

1. Usuário se conecta ao carregador
2. Identifica-se o usuário
3. Identifica os eventos pelo OCPP (IA: organiza os eventos)
4. Salva os eventos no perfil do usuário na API SEMS (IA otimiza a estrutura de dados e gera previsões de uso)
5. Calcula o custo
6. Gera a cobrança

**Opção de Aprofundamento C - Esquema da base de dados: defina e documente o esquema de dados da plataforma, como entidades (usuário, unidade, sessão e fatura), atributos, relacionamentos e exemplos de registros simulados que serão usados na sprint 02.**

- Usuário: id, nome, e-mail, veículo_id
- Unidade: id, bloco, número, custo_fixo, num_carregador, carregador_id
- Carregador: id, unidade_id, status
- Veículo: id, usuáro_id, placa, modelo, kW_bateria
- Sessão: id, usuário_id, veiculo_id, duração, kWh, status
- Fatura: id, unidade_id, sessão_id, usuário_id

**Diagrama da solucao**

## MODELO DE RATEIO DEFINIDO

Perante a prestação do sistema de carregamento compartilhado pelo condomínio residencial, é possível que a gestão financeira utilize o rateio na precificação da atividade do equipamento através de softwares de controle de consumo dos moradores e consumidores do serviço, calculando o consumo em kWh utilizados nas margens de horários pré-definidas e verificando o tempo total em cada sessão de recarga. Utilizando o MODBUS e OCPP do HCA G2 teremos um monitoramento do consumo de energia por usuário, tendo os dados organizados através da API SEMS.

**Variáveis usadas:**

- Agendamento de recarga – verifica se usuário estava agendado para aquele ponto de recarga
- Tempo de carregamento – verifica o tempo de utilização no momento de recarga, gerando cobrança adicionais a cada 30 minutos;
- Horário da utilização do equipamento – verifica o horário em que o equipamento foi utilizado gerando cobrança adicional em horário de pico;

## UTILIZACAO DA IA

Uso de IA: A ferramenta de IA foi utilizada nas seguintes etapas:

- Pesquisas de frente - para compressão dos textos das pesquisas inicias de cada frente, facilitando assim a compreensão dos textos por parte da equipe.
- Documento ReadMe - para verificação ortográfica e auxílio na construção do texto, através da sugestão de palavras-chave.
- Diagrama de rateio - recriando o diagrama elaborado pela equipe melhorando elementos visuais, facilitando a compreensão da imagem.

## PLANO PARA SPRINT 2

- Definição arbitraria dos valores unitários por margens de horário
- Desenvolvimento do software em Python para medição do consumo por apartamento e do condomínio em geral utilizando os dados gerados pela API da GoodWe.
- Desenvolver um aplicativo de agendamento dos pontos de recarga.

## REFERENCIAS

- https://mycond.com.br/desafios-para-carregadores-de-carros-eletricos-em-condominios/
- https://metalsol.com.br/carregadores-de-carros-eletricos-o-futuro-da-mobilidade-no-seu-condominio/
- https://use-move.com/2023/12/20/sistemas-de-recarga-de-veiculos-eletricos-em-condominios-o-que-saber-antes-de-instalar/
- https://www.ampeco.com/guides/iso-15118-complete-guide-for-cpos-and-emsps/
- https://www.neocharge.com.br/tudo-sobre/carregador-carro-eletrico/protocolo-ocpp
- https://voltbras.com/tudo-sobre-a-cobranca-de-recargas-de-carros-eletricos-no-brasil/
- https://proev.co.uk/blog/how-to-profit-from-ev-charging-business-models-fast-chargers-revenue-strategies/
- https://smabc.org.br/brasil-chega-a-25-mil-eletropostos-sendo-33-de-carga-rapida/
- https://monitormercantil.com.br/venda-de-carros-eletrificados-dispara-e-cresce-655-em-2026/
- Protocolo de Ponto de Carregamento Aberto - Wikipédia
- Modbus - Wikipedia
- RFID: o que é, como funciona e aplicações dessa tecnologia - TOTVS
- LAN x MAN x WAN: entenda as diferenças entre os tipos de rede | G1
- Bluetooth Technology Overview | Bluetooth® Technology Website
