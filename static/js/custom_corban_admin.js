document.addEventListener('DOMContentLoaded', function() {
    const corbanSelect = document.querySelector('#id_parent_corban');
    const produtoSelect = document.querySelector('#id_produtos');
    const currentCorbanIdField = document.querySelector('#id_current_corban_id');

    function updateProdutoOptions(produtos, produtosSelecionados) {
        produtoSelect.innerHTML = ''; // Limpa as opções existentes
        produtos.forEach(produto => {
            let isSelected = produtosSelecionados.some(p => p.id === produto.id);
            let option = new Option(produto.nome, produto.id, isSelected, isSelected);
            produtoSelect.add(option);
        });
    }

    function loadInitialProdutos(corbanId) {
        fetch(`/get-corban/${corbanId}`)
            .then(response => response.json())
            .then(data => {
                updateProdutoOptions(data.produtos, data.produtos);
            });
    }

    corbanSelect.addEventListener('change', function() {
        loadInitialProdutos(this.value);
    });

    // Carrega os produtos iniciais com base no Corban atual
    const currentCorbanId = currentCorbanIdField.value;
    if (currentCorbanId) {
        loadInitialProdutos(currentCorbanId);
    }
});
