(function() {
    // Verificar se o jQuery está carregado, caso contrário, carregar de forma síncrona
    if (typeof window.django !== 'undefined' && typeof window.django.jQuery === 'undefined') {
        var script = document.createElement('script');
        script.type = 'text/javascript';
        script.src = 'https://code.jquery.com/jquery-3.6.4.min.js';  // Altere para a versão desejada do jQuery
        document.head.appendChild(script);
        var linkBootstrapGrid = document.createElement('link');
        linkBootstrapGrid.rel = 'stylesheet';
        linkBootstrapGrid.href = 'https://cdn.jsdelivr.net/npm/bootstrap-4-grid@3.4.0/css/grid.min.css';
        document.head.appendChild(linkBootstrapGrid);
    }


    window.cancelarContrato = function(contartoid, nomePlano, idBeneficios) {
        console.log(contratoId)
        var urlAtual = window.location.href;
        var match = urlAtual.match(/\/cliente\/(\d+)/);
        if (match && match[1]) {
            var contratoId = match[1];
        } else {
            console.log("Número do cliente não encontrado na URL.");
        }
        var motivoSelecionado = null;

        // Obter todos os elementos de rádio com o nome "reason"
        var radios = document.getElementsByName('reason');

        // Percorrer os elementos e verificar qual está marcado
        for (var i = 0; i < radios.length; i++) {
            if (radios[i].checked) {
                motivoSelecionado = radios[i].value;
                break; // Se encontrar um marcado, não precisa continuar verificando
            }
        }
        if (motivoSelecionado !== null) {
            console.log(motivoSelecionado);
            // Adicione o código desejado para cancelar o contrato aqui
            console.log('Contrato cancelado! ', contratoId);
            var csrfToken = document.getElementsByName('csrfmiddlewaretoken')[0].value;
            fetch('/api/cartao-beneficio/cancelamento-planos/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                },
                body: JSON.stringify({
                    id_cliente: contratoId,
                    id_cancelamento: motivoSelecionado,
                    nome_plano: nomePlano,
                    id_contrato: contartoid,
                    id_beneficio: idBeneficios,
                }),
            })
            .then(async response => {
                if (!response.ok) {
                    const errorData = await response.json();
                    const errorMessage = errorData.Erro || errorData.message || errorData.detail || 'Erro desconhecido ao cancelar contrato';
                    const mensagemErroDiv = document.getElementById('mensagemErro');
                    mensagemErroDiv.innerText = `Erro ao cancelar contrato: ${errorMessage}`;
                    mensagemErroDiv.style.display = 'block'; // Mostra a mensagem de erro
                }
                else{
                    const mensagemErroDiv = document.getElementById('mensagemSucesso');
                    mensagemErroDiv.innerText = `Plano Cancelado: ${contratoId}`;
                    mensagemErroDiv.style.display = 'block'; // Mostra a mensagem de erro
                    document.querySelector("body > div:nth-child(5) > li > div > div > div.modalHeader > button").click();
                }
            })
            .then(data => {
                console.log('Contrato cancelado com sucesso:', data);
            })
            .catch(error => {
                console.error('Erro ao cancelar contrato:', error);
            });
        }
        else{
            alert('Selecione um motivo para cancelar o contrato');
        }
    }

    window.envioArrecadacao = function(contratoId, nomePlano, idBeneficios) {
        var urlAtual = window.location.href;
        var match = urlAtual.match(/\/cliente\/(\d+)/);
        if (match && match[1]) {
            var id_cliente = match[1];
        } else {
            console.log("Número do cliente não encontrado na URL.");
        }
        var csrfToken = document.getElementsByName('csrfmiddlewaretoken')[0].value;
        fetch('/api/cartao-beneficio/arrecadacao-planos/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({
                id_cliente: id_cliente,
                nome_plano: nomePlano,
                id_contrato: contratoId,
                id_beneficio: idBeneficios,
            }),
        })
        .then(async response => {
            if (!response.ok) {
                const errorData = await response.json();
                const errorMessage = errorData.Erro || errorData.message || errorData.detail || 'Erro desconhecido ao cancelar contrato';
                console.log(`Erro ao cancelar contrato: ${errorMessage}`);
            }
            else{
                console.log(`Plano Cancelado: ${contratoId}`);
            }
        })
        .then(data => {
            console.log('Contrato cancelado com sucesso:', data);
        })
        .catch(error => {
            console.error('Erro ao cancelar contrato:', error);
        });
    }

    function confirmarCancelamento(contratoId, nomePlano, idBeneficios) {
        var styleElement = document.createElement("style");
        var modalContainer = document.createElement("div");
        var jsScriptElement = document.createElement("script");
        jsScriptElement.innerHTML = `
            var modalss = Array.from(document.getElementsByClassName("modalBox"));
            modalss.forEach((modalBox) => {
                const modal = modalBox.querySelectorAll(".modalBackdrop")[0];
                const modalBtn = modalBox.querySelectorAll(".modalBtn")[0];
                const cancelarBtn = modalBox.querySelectorAll(".modalCancelBtn")[0];
                const closeBtn = modalBox.querySelectorAll(".modalCloseBtn")[0];
                const saveBtn = modalBox.querySelectorAll(".modalSaveBtn")[0];
                const form = modalBox.querySelectorAll("form")[0];
                const closeFromEsc = (event) => {
                    if (event.keyCode === 27) { // 27 | ESC
                        hideAndRemoveModal();
                    }
                }
                const showModal = () => {
                    modal.style.display = "flex";
                    document.addEventListener("keydown", closeFromEsc);
                };
                const hideAndRemoveModal = () => {
                    modalBox.remove();
                    document.removeEventListener("keydown", closeFromEsc);
                };
                const hideModal = () => {
                    modal.style.display = "none";
                    document.removeEventListener("keydown", closeFromEsc);
                };
                modalBtn.onclick = showModal;
                cancelarBtn.onclick = hideAndRemoveModal;
                closeBtn.onclick = hideAndRemoveModal;
                document.addEventListener("DOMContentLoaded", function () {
                    var btnBackOffice = document.getElementById("btnBackOffice");
                    btnBackOffice.addEventListener("click", function () {
                        btnBackOffice.disabled = true;
                    });
                });
                form.addEventListener('submit', (event) => {
                    // Set the CSRF token in the form data before submitting
                    var csrfTokenInput = document.createElement("input");
                    var csrfToken = document.querySelector('input[name="csrfmiddlewaretoken"]').value;
                    console.log(csrfTokenInput);
                    csrfTokenInput.type = "hidden";
                    csrfTokenInput.name = "csrfmiddlewaretoken";
                    csrfTokenInput.value = csrfToken;
                    form.appendChild(csrfTokenInput);
                    saveBtn.disabled = true;
                });
                modal.addEventListener('click', (event) => {
                    if (event.target === modal) {
                        hideModal();
                    }
                });
            });
        `;
        styleElement.innerHTML = `
            .modalBackdrop {
                display: flex;
                position: fixed;
                z-index: 99999;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                overflow: auto;
                background-color: rgba(0, 0, 0, 0.4);
                align-items: center;
                justify-content: center;
            }
            .modal {
                width: 550px;
                max-width: 90%;
                border-radius: 10px;
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
                overflow: auto;
                z-index: 100000; /* Defina um valor maior do que o z-index do .modalBackdrop */
            }
            .modal .modalHeader {
                background-color: var(--admin-interface-module-background-color);
                padding: 12px 24px;
                color: var(--admin-interface-module-text-color);
                display: flex;
                align-items: center;
                justify-content: space-between;
            }
            .modal .modalHeader .modalTitle {
                margin: 0;
            }
            .modal .modalHeader .modalCloseBtn {
                font-size: 28px;
                font-weight: bold;
                color: var(--admin-interface-module-text-color);
                background-color: transparent;
                border-radius: 10px;
                border: none;
                height: 30px;
                width: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .modal .modalHeader .modalCloseBtn:hover,
            .modal .modalHeader .modalCloseBtn:focus {
                cursor: pointer;
                background-color: rgba(255, 255, 255, 0.15);
            }
            .modal .modalContent {
                background-color: #fefefe;
                padding: 20px;
            }
            .modal .modalContent .modalText {
                margin: 0;
                font-weight: normal;
            }
            .modal .modalContent form textarea {
                width: 100%;
                margin-top: 10px;
                box-sizing: border-box;
                resize: vertical;
                min-height: 60px;
            }
            .modal .modalFooter {
                display: flex;
                justify-content: end;
                gap: 8px;
                margin-top: 20px;
                flex-wrap: wrap;
            }
            .modalCloseBtn:hover{
                cursor:pointer;
                background-color: black;
            }

        `;
        modalContainer.innerHTML = `
            <li class="objectaction-item modalBox">
                <a class="btn modalBtn btnSuccess" title="Aprovar contrato"></a>
                <div class="modalBackdrop">
                    <div class="lixo" style="
                    width: 550px;
                    border-radius: 10px;
                    max-width: 90%;
                    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
                    overflow: auto;
                    background: white;
                    z-index: 100000; /* Defina um valor maior do que o z-index do .modalBackdrop */
                ">
                <div class="modalHeader" style="
                    background-color: var(--admin-interface-module-background-color);
                    padding: 12px 24px;
                    color: var(--admin-interface-module-text-color);
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                ">
                    <h2 class="modalTitle" style="font-size: 1rem;color: white;font-weight: bold;">ATENÇÃO</h2>
                    <button class="modalCloseBtn" style="
                        font-size: 28px;
                        font-weight: bold;
                        color: var(--admin-interface-module-text-color);
                        background-color: transparent;
                        border-radius: 10px;
                        border: none;
                        height: 30px;
                        width: 30px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        transition: background-color 0.3s; /* Adiciona uma transição suave */
                    " onmouseover="this.style.backgroundColor='rgba(255, 255, 255, 0.15)'"
                    onmouseout="this.style.backgroundColor='transparent'">×</button>
                 </div>
                <div class="modalContent" style="
                    background-color: #fefefe;
                    padding: 20px;
                ">
                    <h2 class="modalText" style="background: white; color: black; font-size: 1rem;">Deseja mesmo cancelar os planos desse contrato?</h2>
                    <div id="mensagemErro" class="modalErrorMessage" style="color: red;"></div>
                    <div id="mensagemSucesso" class="modalErrorMessage" style="color: green;"></div>
                    <div>
                        <div class="modalCheckboxList">
                            <label>
                                <input type="radio" name="reason" value="001">    Cancelamento a pedido
                            </label>
                            <br>
                            <label>
                                <input type="radio" name="reason" value="002">    Cancelamento por inadimplência
                            </label>
                            <br>
                            <label>
                                <input type="radio" name="reason" value="003">    Cancelamento por sinistro
                            </label>
                            <br>
                            <label>
                                <input type="radio" name="reason" value="004">    Por troca de plano
                            </label>
                        </div>
                        <div class="modalFooter" style="margin-top: 0px;display: flex;justify-content: end;gap: 8px;margin-top: 20px;flex-wrap: wrap;">
                            <button type="button" class="btn modalActionBtn btnDanger modalCancelBtn" style="background-color: #DD4646 !important;border-radius: 4px;padding: 8px 16px;color: var(--admin-interface-module-text-color);border: none;">
                                NÃO
                            </button>
                            <button type="button" onclick="cancelarContrato('${contratoId}', '${nomePlano}', '${idBeneficios}')" class="btn modalActionBtn btnSuccess modalSaveBtn" style="background-color: #44B78B !important;border-radius: 4px;padding: 8px 16px;color: var(--admin-interface-module-text-color);border: none;">
                                SIM
                            </button>
                        </div>
                    </div>
                </div>
            </li>
        `;

        // Adicionar o modalContainer como filho do elemento pai
        document.body.appendChild(modalContainer);//Adicionar o modalContainer ao final do corpo do documento
        document.head.appendChild(styleElement);
        document.head.appendChild(jsScriptElement);
    }

    // Adicione um evento de clique personalizado ao botão de ação
    document.addEventListener('DOMContentLoaded', function() {
        var tabelaDentroDaDiv = document.getElementById('tabcontent-seguro-beneficio').querySelector('table');
        var novoTh = document.createElement('th');
        novoTh.textContent = 'Cancelar Plano'; // Adicione o texto desejado ao cabeçalho

        var cabecalho = tabelaDentroDaDiv.querySelector('thead tr');
        cabecalho.appendChild(novoTh);

        var novoTht = document.createElement('th');
        novoTht.textContent = 'Enviar arrecadação'; // Adicione o texto desejado ao cabeçalho

        var cabecalhot = tabelaDentroDaDiv.querySelector('thead tr');
        cabecalhot.appendChild(novoTht);

        var linhas = tabelaDentroDaDiv.querySelectorAll('tbody tr');
        var elements = document.querySelectorAll('.inline-group .tabular td.original p');

        elements.forEach(function(element) {
            element.style.height = "100%";
        });

        linhas.forEach(function (linha) {
            var contratoid = linha.querySelector('.field-contrato_emprestimo p').textContent;
            var nomePlanoTexto = linha.querySelector('.field-nome_plano p').textContent;
            var nomePlanoOperadora = linha.querySelector('.field-nome_operadora p').textContent;
            var idBeneficios = linha.querySelector('.field-id.hidden p').textContent;

            var novoTd = document.createElement('td');
            var novoBotao = document.createElement('button');
            novoBotao.setAttribute('type', 'button');
            // novoBotao.setAttribute('onclick', 'cancelarContrato(${nomePlanoTexto})');
            novoBotao.setAttribute('class', 'btn modalActionBtn btnSuccess modalSaveBtn');
            novoBotao.setAttribute('style', 'background-color: #DD4646 !important; border-radius: 4px; padding: 8px 16px; color: var(--admin-interface-module-text-color); border: none;');
            novoBotao.textContent = 'Cancelar Plano'  // Usando o texto do nome do plano no botão

            if (nomePlanoOperadora !== 'Sabemi' && nomePlanoOperadora !== 'Tem Saúde') {
                novoBotao.addEventListener('click', function() {
                    confirmarCancelamento(contratoid, nomePlanoTexto, idBeneficios);
                });
            } else {
                novoBotao.setAttribute('disabled', true);
            }
            // Adicionando o botão ao novo td
            novoTd.appendChild(novoBotao);

            // Adicionando o novo td à linha atual
            linha.appendChild(novoTd);

            var novoTd = document.createElement('td');envioArrecadacao
            var novoBotao = document.createElement('button');
            novoBotao.setAttribute('type', 'button');
            // novoBotao.setAttribute('onclick', 'cancelarContrato(${nomePlanoTexto})');
            novoBotao.setAttribute('class', 'btn modalActionBtn btnSuccess modalSaveBtn');
            novoBotao.setAttribute('style', 'background-color: #70BF2B !important; border-radius: 4px; padding: 8px 16px; color: var(--admin-interface-module-text-color); border: none;');
            novoBotao.textContent = 'Enviar Arrecadação'  // Usando o texto do nome do plano no botão

            if (nomePlanoOperadora !== 'Sabemi' && nomePlanoOperadora !== 'Tem Saúde') {
                novoBotao.addEventListener('click', function() {
                    envioArrecadacao(contratoid, nomePlanoTexto, idBeneficios);
                });
            } else {
                novoBotao.setAttribute('disabled', true);
            }
            // Adicionando o botão ao novo td
            novoTd.appendChild(novoBotao);

            // Adicionando o novo td à linha atual
            linha.appendChild(novoTd);
        });
    });
})();
