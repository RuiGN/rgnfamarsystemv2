"""Instruções passo-a-passo para o manual do ERP RGN Farma System.

Cada entrada descreve como realizar operações comuns no sistema,
organizadas por módulo. Estas instruções complementam o manual_catalog.py.
"""

STEP_BY_STEP_GUIDES = {
    'formulations': """
## Como criar uma fórmula mestra

1. No menu lateral, clique em **Fórmulas e roteiros**.
2. Clique no recurso **Fórmulas mestras**.
3. Clique no botão **Novo registro** (canto superior direito).
4. Preencha os campos:
   - **Código**: identificador único da fórmula (ex: FM-001).
   - **Versão**: versão da fórmula (ex: 1).
   - **Produto**: selecione o produto acabado ao qual esta fórmula se aplica.
   - **Data de vigência inicial**: quando a fórmula entra em vigor.
   - **Data de vigência final** (opcional): quando expira.
5. Clique em **Salvar**.
6. Para adicionar componentes (matérias-primas), na tela de detalhe da fórmula,
   use a seção **Componentes da fórmula** (inline tabular):
   - **Linha**: número sequencial (preenchido automaticamente).
   - **Material**: selecione a matéria-prima no cadastro de produtos.
   - **Função**: papel do componente (ativo, excipiente, adjuvante, etc.).
   - **Quantidade**: quantidade necessária.
   - **Unidade**: unidade de medida (mg, g, mL, etc.).
   - **Perda prevista (%)**: percentual de perda esperado na produção.
   - **Fator de conversão**: se aplicável.
7. Clique em **Salvar** para registrar cada componente.
8. A fórmula pode ser visualizada em árvore (botão **Árvore / BOM**).

## Como criar um roteiro de fabricação

1. No menu lateral, clique em **Fórmulas e roteiros**.
2. Clique no recurso **Roteiros**.
3. Clique em **Novo registro**.
4. Preencha:
   - **Código**: identificador do roteiro.
   - **Versão**: versão.
   - **Produto**: produto ao qual o roteiro se aplica.
   - **Fórmula**: fórmula mestra vinculada.
   - **Status**: defina como rascunho ou aprovado.
   - **Vigência**: datas de início e fim.
5. Clique em **Salvar**.
6. Para adicionar etapas do roteiro, use o recurso **Etapas de roteiro**:
   - Informe sequência, descrição da operação, tempo setup, tempo processo e
     área.
""",
    'production': """
## Como criar uma ordem de produção

1. No menu lateral, clique em **Produção**.
2. Clique no recurso **Ordens de produção**.
3. Clique em **Novo registro**.
4. Preencha os campos:
   - **Número**: gerado automaticamente (OP-XXX).
   - **Produto**: produto a ser fabricado.
   - **Fórmula**: fórmula mestra do produto.
   - **Roteiro**: roteiro de fabricação.
   - **Quantidade planejada**: quantidade a produzir.
   - **Unidade**: unidade de medida.
   - **Data prevista de início** e **fim**.
5. Clique em **Salvar**.
6. A ordem passa por transições de status:
   - **Rascunho** → **Aprovada** (ação: Aprovar)
   - **Aprovada** → **Liberada** (ação: Liberar)
   - **Liberada** → **Em andamento** (ação: Iniciar)
   - **Em andamento** → **Pausada** ou **Concluída**
   - Qualquer status ativo → **Cancelada** (com justificativa)
7. Para registrar consumo de matéria-prima, use **Consumo de materiais** no detalhe da ordem.
8. Para registrar resultados de produção, use **Resultados de produção**.
9. Os **Mapas de controle** e **Mapa de resultados** estão disponíveis no detalhe da ordem.

## Como registrar consumo de matéria-prima

1. Abra a ordem de produção no detalhe.
2. Na seção **Consumo de materiais**, clique em adicionar.
3. Selecione o componente da fórmula, a quantidade real consumida e o lote de estoque.
4. Salve. O sistema atualiza o saldo de estoque automaticamente.

## Como receber resultados de produção

1. Abra a ordem de produção no detalhe.
2. Na seção **Resultados de produção**, registre a quantidade produzida, lote gerado e qualidade.
3. Use a ação **Receber resultados** para transformar resultados pendentes em recebidos.
4. O sistema cria automaticamente o movimento de entrada de estoque.
""",
    'crm': """
## Como criar um pedido de venda

1. No menu lateral, clique em **CRM**.
2. Clique no recurso **Pedidos de venda**.
3. Clique em **Novo registro**.
4. Preencha:
   - **Cliente**: selecione o cliente cadastrado.
   - **Representante** (opcional): vendedor responsável.
   - **Data de entrega solicitada**: prazo desejado.
   - **Condição de pagamento**: condições comerciais.
5. Clique em **Salvar** para criar o cabeçalho.
6. Na seção **Itens do pedido** (inline), adicione produtos:
   - **Produto**: selecione do catálogo.
   - **Quantidade** e **Unidade**.
   - **Preço unitário** e **Desconto (%)**.
7. Salve. O sistema calcula o valor total automaticamente.
8. O pedido pode ser **Aprovado**, **Atendido** ou **Cancelado**.

## Como criar uma oportunidade (CRM Kanban)

1. No menu lateral, clique em **CRM**.
2. Clique no recurso **Oportunidades**.
3. Clique em **Novo registro**.
4. Preencha: cliente, título, valor estimado, data prevista de fechamento e estágio.
5. Os estágios são: Lead → Qualificada → Proposta → Negociação → Ganha/Perdida.
6. Use a visão Kanban para arrastar oportunidades entre estágios.
""",
    'finance': """
## Como registrar um título a pagar

1. No menu lateral, clique em **Financeiro**.
2. Clique no recurso **Títulos**.
3. Clique em **Novo registro**.
4. Selecione tipo: **Conta a pagar**.
5. Preencha: parceiro (fornecedor), valor original, data de vencimento, categoria financeira.
6. Salve. O título fica como **Pendente**.
7. Para baixar (pagar), use a ação de baixa no detalhe do título: informe conta financeira, data e valor.
8. O sistema atualiza o saldo da conta e gera o fluxo de caixa.

## Como registrar um título a receber

1. Siga os mesmos passos acima, mas selecione tipo: **Conta a receber**.
2. O parceiro deve ser um cliente.
3. Para baixar (receber), use a ação de baixa no detalhe.

## Como criar uma conta financeira

1. No recurso **Contas financeiras**, clique em **Novo registro**.
2. Preencha: código, nome, tipo (Caixa ou Banco), saldo inicial.
3. Para bancos: informe nome do banco, agência e número da conta.
""",
    'inventory': """
## Como dar entrada no estoque

1. A entrada de estoque acontece automaticamente quando:
   - Um **recebimento de compra** é confirmado (módulo Compras).
   - Um **resultado de produção** é recebido (módulo Produção).
2. Para entradas manuais, use o recurso **Movimentações de estoque**:
   - Tipo: **Entrada**.
   - Produto, lote, quantidade, almoxarifado e localização.
3. O sistema cria o **saldo de estoque** automaticamente.

## Como consultar o saldo de estoque

1. No menu lateral, clique em **Estoque**.
2. Clique no recurso **Saldos de estoque**.
3. Filtre por produto, almoxarifado ou situação de qualidade.
4. O sistema mostra: produto, lote, quantidade, reservado, disponível, validade.

## Como verificar lotes vencendo

1. No recurso **Lotes de estoque**, filtre por data de validade.
2. Ou use o relatório **Lotes próximos do vencimento** (Relatórios → Administrativos).
""",
    'procurement': """
## Como criar um pedido de compra

1. No menu lateral, clique em **Compras**.
2. Clique no recurso **Pedidos de compra**.
3. Clique em **Novo registro**.
4. Preencha: fornecedor, data de emissão, condição de pagamento.
5. Na seção de itens, adicione produtos, quantidades e preços.
6. Salve. O pedido passa por: Rascunho → Aprovado → Enviado → Parcialmente recebido → Recebido.

## Como registrar recebimento de compra

1. Abra o pedido de compra no detalhe.
2. Use a ação de recebimento: informe quantidade recebida, lote, validade.
3. O sistema cria automaticamente a entrada de estoque e o título a pagar.
""",
    'masters': """
## Como cadastrar um produto

1. No menu lateral, clique em **Cadastros**.
2. Clique no recurso **Produtos**.
3. Clique em **Novo registro**.
4. Preencha: código, descrição, tipo (matéria-prima, produto acabado, etc.),
   unidade de medida, NCM, status.
5. Salve.

## Como cadastrar um parceiro (cliente/fornecedor)

1. No recurso **Parceiros**, clique em **Novo registro**.
2. Preencha: código, razão social, nome fantasia, CNPJ/CPF, tipo (cliente, fornecedor, etc.).
3. Informe endereço, contato e dados comerciais.
4. Salve.
""",
    'fiscal': """
## Como emitir uma nota fiscal

1. No menu lateral, clique em **Fiscal**.
2. Clique no recurso **Documentos fiscais**.
3. Clique em **Novo registro**.
4. Preencha: tipo (entrada/saída), operação (compra/venda/devolução), parceiro,
   número, série, data de emissão.
5. Na seção de itens, adicione: produto, CFOP, NCM, quantidade, valor, tributos.
6. Salve. O documento passa por: Rascunho → Em conferência → Conferida → Aprovada → Lançada.
7. Após aprovada, o sistema pode gerar o título financeiro automaticamente.

## Como consultar apuração de impostos

1. Use o recurso **Apurações tributárias**.
2. Clique em **Novo registro** para criar uma apuração de período.
3. Selecione o tributo (ICMS, PIS, COFINS, CBS, IBS) e o período.
4. O sistema calcula débitos, créditos e valor a recolher.
""",
    'quality': """
## Como registrar uma inspeção de qualidade

1. No menu lateral, clique em **Qualidade**.
2. Clique no recurso **Inspeções**.
3. Clique em **Novo registro**.
4. Preencha: produto/lote, tipo de inspeção, responsável, amostragem.
5. Na seção de resultados, informe cada parâmetro e seu resultado.
6. O sistema classifica como conforme, não-conforme ou fora de especificação.
""",
    'capa': """
## Como criar uma ação corretiva

1. No menu lateral, clique em **CAPA**.
2. Clique no recurso **Ações corretivas**.
3. Clique em **Novo registro**.
4. Preencha: título, descrição, responsável, prazo, origem (desvio, reclamo, auditoria).
5. O CAPA passa por: Aberta → Em andamento → Implementada → Verificada → Fechada.
""",
    'agenda': """
## Como criar uma tarefa

1. No menu lateral, clique em **Agenda**.
2. Clique no recurso **Tarefas**.
3. Clique em **Novo registro**.
4. Preencha: título, descrição, responsável, data de vencimento, prioridade.
5. A tarefa pode ser visualizada em calendário (visão Calendário).
""",
    'commissions': """
## Como cadastrar uma comissão

1. No menu lateral, clique em **Comissões**.
2. Clique no recurso **Avaliações de comissão**.
3. Clique em **Novo registro**.
4. Preencha: representante, competência (mês/ano), valor base, percentual.
5. Salve. A comissão pode ser aprovada e vinculada a um título a pagar.
""",
}


def get_step_by_step(module_slug):
    """Retorna as instruções passo-a-passo para um módulo, ou string vazia."""
    return STEP_BY_STEP_GUIDES.get(module_slug, '')
