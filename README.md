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
