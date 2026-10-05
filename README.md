# Bolsa Brasil

MVP desktop em Python e Tkinter para acompanhar o mercado brasileiro. A primeira tela exibe o gráfico intradiário do Ibovespa (`^BVSP`) e atualiza os dados uma vez por minuto.

## Executar

Requer Python 3.10 ou mais recente.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py
```

O Yahoo Finance é usado como fonte inicial e pode apresentar atraso, indisponibilidade ou diferenças em relação aos dados oficiais. Para uso profissional ou baixa latência, substitua o provedor por uma API licenciada da B3 ou de uma corretora.

## Painel e busca de ativos

Use **Acrescentar gráfico/cotação** e digite ao menos três caracteres do ticker ou nome.
Clicar em um resultado abre uma prévia com gráfico, preço e seleção de período.
**Acrescentar à tela inicial** salva o ativo no painel. Os cartões são distribuídos
em até três colunas, com 12 ativos por aba e até quatro abas (48 ativos).
Há rolagem vertical, ampliação e remoção de cartões. Ativos repetidos direcionam
para a aba existente. Cada gráfico possui seu próprio período.

Na faixa superior, escolha um período e clique em **Aplicar à aba** para atualizar
todos os gráficos da aba selecionada; as demais abas mantêm seus períodos.

### Reorganizar gráficos

Arraste pela alça **⋮⋮** no cabeçalho do cartão e solte sobre outra posição.
Para mudar de aba, passe sobre o título da aba de destino e solte ali (acrescenta
ao final), ou continue até a posição desejada no painel. Use **+ Nova aba** para
criar uma aba vazia; continuam valendo os limites de quatro abas e 12 gráficos
por aba. Abas cheias recusam a transferência. Soltar fora do painel ou pressionar
Esc cancela. A nova ordem é salva automaticamente e o período do cartão é mantido.

### Informações e indicadores

O botão **Informações** em cada gráfico abre indicadores agrupados em Valuation,
Endividamento, Eficiência e Rentabilidade: P/L, P/VP, DY de 12 meses, LPA, VPA,
EV/EBITDA, P/Receita, dívida líquida/EBITDA, dívida/patrimônio, liquidez,
margens, ROE e ROA. Cada linha identifica sua definição/metodologia.
Na carteira, clique em um ativo da composição geral ou do detalhamento de uma
classe e escolha **Informações e indicadores**. Enter também abre a seleção.

A organização usa o [Status Invest](https://statusinvest.com.br/acoes/petr4) como
referência. Os dados são do Yahoo Finance, com horário de consulta, trimestre
reportado e cache de cinco minutos; metodologias e períodos podem diferir entre
provedores. Campos ausentes aparecem como **—**, nunca como zero. Dívida líquida
é calculada como dívida total menos caixa, sem ajustes adicionais. Fundos recebem
apenas indicadores compatíveis disponíveis. Indicadores empresariais não se aplicam
a moedas, criptomoedas ou índices.

## Câmbio

A busca inclui 20 moedas contra o real: USD, EUR, JPY, CNY, GBP, CHF, CAD,
AUD, NZD, HKD, SGD, MXN, ARS, CLP, ZAR, INR, KRW, SEK, NOK e DKK.
Busque pelo código ou nome em português, como `dólar`, `euro`, `iene` ou `yuan`.
O par `JPY/BRL`, por exemplo, mostra o valor de **1 iene em reais**, com seis
casas decimais. Cada par aceita os mesmos períodos e pode ser salvo no painel.
A disponibilidade do histórico depende do Yahoo Finance; indisponibilidades
aparecem no cartão.

Na carteira, selecione a classe **Moedas**. Quantidade é o número de unidades da
moeda estrangeira e preço unitário é em BRL (ex.: 100 USD comprados a R$ 5 cada).
A avaliação usa o par direto contra o real e participa do total normalmente.

## Criptomoedas e ativos americanos

A busca também consulta o Yahoo Finance por tickers e nomes de ativos americanos
e criptomoedas. Experimente `BTC`, `ETH`, `AAPL`, `NVDA` ou `SPY`. A partir de três
caracteres, a consulta online é automática; para códigos curtos como `F` ou `V`,
pressione Enter ou **Buscar online**. Os resultados dependem da cobertura do Yahoo.

Esses gráficos começam em **US$** e possuem **Ver em R$ / Ver em US$** ao lado
do preço. A conversão usa a última taxa disponível de `BRL=X`, com data exibida.
Todos os pontos do gráfico são multiplicados pela mesma taxa: trata-se de uma
conversão visual, não de uma série de retornos incluindo variação histórica do câmbio.
Se o câmbio estiver indisponível, o gráfico permanece em dólares.

Na carteira, use as classes **Criptomoedas**, **Ações EUA** ou **ETFs EUA**, com
preço unitário em dólares. Quantidades fracionárias são aceitas. As cotações são
exibidas na moeda original por padrão, com botão para mostrá-las em reais.
Totais e percentuais consolidam os valores em uma única moeda (BRL por padrão),
com botão para alternar o total para USD. A ausência de câmbio torna os totais
dependentes indisponíveis. O Excel passa a incluir a coluna **Moeda**; arquivos
antigos continuam sendo lidos como BRL e são atualizados na próxima gravação,
com backup. O preço histórico de cada operação mantém a moeda original.

## Criar e abrir carteiras

Clique em **Criar carteira** e escolha onde salvar o arquivo `.xlsx`.
**Abrir carteira** recupera um arquivo já criado pelo aplicativo. É possível
manter carteiras distintas em arquivos diferentes.

Em **Lançar compra/venda**, informe ticker, nome, classe, operação, data,
quantidade e preço unitário da negociação. A busca do ticker sugere ativos e
preenche nome/classe quando disponíveis; a classe pode ser ajustada antes de salvar.
Use vírgula para decimais (por exemplo `12,50`). Cada lançamento é salvo imediatamente.

A aba **Operações** do Excel contém ID, Data, Ticker, Nome, Classe, Operação,
Quantidade e Preço unitário (R$), com datas e números armazenados como valores.
O app lê esse arquivo como fonte dos lançamentos. Preserve o cabeçalho e os IDs
ao editar no Excel e use **Recarregar Excel** após salvar alterações externas.
Gravações detectam alterações externas e mantêm a versão anterior em `.backup.xlsx`.
Uma carteira existente nunca é sobrescrita pelo botão Criar.

O valor atual é quantidade em posição × última cotação disponível do Yahoo Finance.
Compras aumentam o saldo e vendas o reduzem. Vendas acima do saldo na data são
recusadas; no mesmo dia, vale a ordem de lançamento. Não há posições vendidas
a descoberto nesta versão. As quantidades não são ajustadas automaticamente por
desdobramentos, grupamentos ou outros eventos corporativos.

A janela mostra gráficos circulares e tabelas por classe e por ativo. Clique em
uma classe para abrir seu gráfico e sua lista de ativos, com valores em reais e
percentuais sobre a classe. As cores por ativo são estáveis em todas as janelas.
Na visão geral, os percentuais têm como base o total da carteira. Valores zerados
não geram fatias, e cotações ausentes deixam totais/percentuais dependentes indisponíveis.

Use **Atualizar cotações** para atualizar a avaliação. Cada item informa a data
da última cotação; pode ser do último pregão. A carteira não inclui caixa, taxas,
impostos, dividendos ou proventos. As operações podem ser consultadas e excluídas
na guia **Operações registradas**, com confirmação e validação do saldo restante.

Testes: `python -m unittest discover -s tests -v`.

O painel e o catálogo são salvos em `.bolsa_data/`. A busca usa todas as páginas
do catálogo público da brapi, atualizado na abertura, com cópia local para uso
offline. A cobertura inclui ações, FIIs, ETFs e BDRs disponíveis nesse provedor;
não representa garantia de todos os instrumentos da B3 (opções e futuros não
estão integrados). Cotação e histórico dependem da cobertura do Yahoo Finance.
Um ativo sem histórico apresenta uma mensagem no cartão.

A variação exibida é entre o primeiro e o último preço do período selecionado,
não necessariamente a variação sobre o fechamento anterior. Hoje mostra a sessão
mais recente disponível, identificada pela data do último dado, em horário de Brasília.

## Próximas etapas

1. Expandir provedores e cobertura de instrumentos.
2. Adicionar indicadores e informações sobre proventos.
3. Exportar e importar a configuração do painel.
4. Adicionar candles e volume.
5. Criar alertas de preço e acompanhamento de rentabilidade.
# Eventos corporativos manuais

No formulário de liquidação, **Calcular liquidação pelos valores por cota…**
reconstrói a posição na data (incluindo desdobramentos e excluindo operações
posteriores). Informe o valor entregue em novas cotas por cota antiga, dinheiro
bruto por cota antiga, retenções totais e dinheiro adicional de frações recebido.
O custo por cota nova é o valor em cotas dividido pelo fator; o líquido é a
quantidade antiga × dinheiro por cota − descontos + dinheiro de frações.
O resultado é uma estimativa conferível: a quantidade sugerida é a parte inteira,
o líquido é arredondado a centavos, e os campos continuam editáveis conforme o
extrato. Não há busca automática de parâmetros ou cálculo tributário. Recalcule
se alterar data, fator ou parâmetros. Apenas os resultados confirmados são
gravados no evento; os parâmetros auxiliares da calculadora não são persistidos.

Ao corrigir a classe de um ativo na aba Operações do Excel, corrija todos os
lançamentos desse ticker e use **Recarregar Excel** no app. A classe de origem
dos eventos acompanha a posição recalculada quando moeda e instrumento não
mudam (por exemplo, Ações → FIIs). Para eventos no mesmo ticker, a classe de
destino também acompanha a correção; destinos com outro ticker mantêm sua
classe explícita. A leitura não sobrescreve o arquivo: a reconciliação é gravada
na próxima gravação pelo app. Ausência de saldo na data continua sendo um erro.

**Liquidação com entrega de cotas:** para eventos que encerram o ativo antigo
e entregam outro ativo mais dinheiro, selecione esse tipo em vez de Incorporação.
Informe a relação de troca, a quantidade efetivamente creditada, o custo unitário
das novas cotas conforme o informe e o dinheiro líquido **total** recebido.
O custo antigo é encerrado e preservado no histórico; não é transferido ao destino.
Se já houver posição no destino, o novo custo é somado ao existente.
O dinheiro é um registro histórico, não um saldo de caixa e não integra o total
de ativos da carteira. Use a data efetiva do evento; este registro não controla
datas separadas de pagamentos. A diferença entre quantidade teórica e creditada
deve ser menor que uma unidade: fica discriminada para conferência, sem cotação,
sem venda automática e sem apuração de imposto. Eventuais recebimentos posteriores
exigem substituir o evento com os valores consolidados; não há conciliação de caixa.
Os valores são manuais: não há preenchimento automático de BCFF11/BTHF11.

Na carteira, abra **Eventos e custo ajustado → Registrar evento corporativo**.
Há suporte a desdobramento, grupamento, troca de ticker/nome, incorporação,
cisão, bonificação e amortização, sem importação da B3. Confira os dados no
comunicado do evento: o aplicativo não descobre nem valida relações de troca
ou critérios fiscais automaticamente.

O fator é a quantidade recebida por unidade antiga (split 1→10: `10`;
grupamento 10→1: `0,1`). Na bonificação, informe somente a proporção adicional
(10%: `0,1`) e o custo por nova unidade. Na cisão, informe o percentual do
custo transferido ao destino; a quantidade da origem permanece inalterada.
Incorporações transferem todo o custo e encerram a posição de origem.
Amortização reduz o custo pelo valor informado por unidade, sem registrar caixa.
Compensações em dinheiro não são calculadas automaticamente (na liquidação,
podem ser informadas). Eventos com redução simultânea da quantidade na cisão
e apuração tributária não são calculados automaticamente.

As operações originais são preservadas; os eventos ficam na aba `Eventos` do
Excel. A carteira é recalculada por data; escolha Antes/Depois das operações
do mesmo dia. Eventos no mesmo dia/momento seguem a ordem de registro.
Frações são mantidas, sem venda ou arredondamento automático. Subscrições
exercidas devem ser lançadas como compras. Transferências entre corretoras não
alteram esta carteira consolidada e não devem ser lançadas como compras/vendas.
Arquivos antigos continuam aceitos. Exclusões também revalidam todo o histórico;
a versão anterior do arquivo fica em `.backup.xlsx`.
# Tema visual e logos

Interface escura com controles e cartões arredondados, abas destacadas e
indicadores em cartões responsivos com símbolos e explicações. O painel usa
até três colunas, reduzindo para duas ou uma em janelas menores. As barras
mantêm suporte a arraste e roda do mouse.

Instale as dependências atualizadas com `pip install -r requirements.txt`.
Os logos são baixados ao abrir cartões e guardados em `.bolsa_data/logos`.
O botão **Logos offline** tenta baixar as imagens de todo o catálogo local,
sem bloquear a interface. As listas usam imagens já em cache; reabra a busca
ou carteira após um download em lote. Sem imagem disponível, há identificação
alternativa. O cache é local e não é enviado ao Git; os logos continuam sendo
marcas de seus respectivos titulares.

Fontes: [brapi](https://brapi.dev/faq/a-api-fornece-acesso-as-logos-das-empresas-listadas-na-b3)
para B3, [Financial Modeling Prep](https://site.financialmodelingprep.com/developer/docs)
para EUA e [Cryptocurrency Icons](https://github.com/spothq/cryptocurrency-icons)
(CC0) para criptomoedas. A disponibilidade não é garantida para todos os ativos.
Conversão SVG usa CairoSVG; em sistemas sem Cairo instale a biblioteca do sistema
(`libcairo2` no Ubuntu/Debian). Falhas de logo não impedem o uso das cotações.
