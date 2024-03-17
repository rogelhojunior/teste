document.addEventListener('DOMContentLoaded', function() {
    const corbanSelect = document.querySelector('#id_corban');
    const nivelHierarquiaSelect = document.querySelector('#id_nivel_hierarquia');
    const produtoSelect = document.querySelector('#id_produtos');
    const supervisorSelect = document.querySelector('#id_supervisor');
    const currentCorbanIdField = document.querySelector('#id_current_corban_id');

    function updateProdutoOptions(produtos, produtosSelecionados) {
        produtoSelect.innerHTML = '';
        produtos.forEach(produto => {
            let isSelected = produtosSelecionados.some(p => p.id === produto.id);
            let option = new Option(produto.nome, produto.id, isSelected, isSelected);
            produtoSelect.add(option);
        });
    }

    function updateSupervisorOptions(supervisores) {
        let valorAtualSupervisor = supervisorSelect.value;
        supervisorSelect.innerHTML = '';

        supervisores.forEach(supervisor => {
            let option = new Option(supervisor.name, supervisor.id);
            option.selected = supervisor.id.toString() === valorAtualSupervisor;
            supervisorSelect.add(option);
        });

        if (!supervisores.some(supervisor => supervisor.id.toString() === valorAtualSupervisor)) {
            supervisorSelect.value = valorAtualSupervisor;
        }
    }

    function fetchData(corbanId, nivelSelecionado) {
        fetch(`/get-corban/${corbanId}?nivel=${nivelSelecionado}`)
            .then(response => response.json())
            .then(data => {
                updateProdutoOptions(data.produtos, data.produtos);
                updateSupervisorOptions(data.supervisores);
            });
    }

    corbanSelect.addEventListener('change', function() {
        fetchData(this.value, nivelHierarquiaSelect.value);
    });

    nivelHierarquiaSelect.addEventListener('change', function() {
        fetchData(corbanSelect.value, this.value);
    });

    if (currentCorbanIdField.value) {
        fetchData(currentCorbanIdField.value, nivelHierarquiaSelect.value);
    }
});
