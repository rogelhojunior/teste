$(document).ready(function () {
    KPIContrato();
    new Splide('.splide', {
        type: 'slide', perPage: 6, perMove: 1, pagination: false, drag: 'free', breakpoints: {
            640: {
                perPage: 2,
            },
        }
    }).mount();
});

function KPIContrato() {

    // Define a loading HTML element
    const loading = '<div class="loadingio-spinner-reload-pb6lozevp3"><div class="ldio-wagf8bzsl1"><div><div></div><div></div><div></div></div></div></div>';

    // Extract URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const type_product = urlParams.get('tipo_produto__exact');
    const status = urlParams.get('status');
    // If 'tipo_produto__exact' exists in URL parameters, store it in localStorage
    if (type_product) {
        localStorage.setItem('type_select_product', type_product);
    }
    // Define mappings between product types and HTML selectors
    const statusMappings_Products = [
        {product: 12, selector: "#portabilidade"},
        {product: 17, selector: "#portabilidade-refinanciamento"},
        {product: 16, selector: "#margem-livre"},
        {product: 7, selector: "#cartao-beneficio"},
        {product: 15, selector: "#cartao-consignado"},
        {product: 14, selector: "#saque-complementar"},
    ];

    // Define mappings between contract statuses and HTML selectors for different product types
    const statusMappings_Port = [
        {status: 33, selector: "#saldo-retornado-port"},
        {status: 42, selector: "#aguardando-in100-digitacao-port"},
        {status: 43, selector: "#aguardando-in100-recalculo-port"},
        {status: 44, selector: "#in100-retornada-recalculo-port"},
        {status: 37, selector: "#aguardando-averbacao-port"},
        {status: 34, selector: "#aguardando-pagamento-port"},
        {status: 41, selector: "#reprovado-port"},
        {status: 38, selector: "#finalizado-port"}
    ];
    const statusMappings_FreeMargin = [
        {status: 42, selector: "#aguardando-in100-margem-livre"},
        {status: 37, selector: "#aguardando-averbacao-margem-livre"},
        {status: 13, selector: "#aguardando-desembolso-margem-livre"},
        {status: 19, selector: "#pendente-correcao-dados-bancarios-margem-livre"},
        {status: 38, selector: "#finalizado-margem-livre"},
        {status: 41, selector: "#reprovado-margem-livre"},
    ];
    const statusMappings_Refin = [
        {status: 55, selector: "#aguardando-averbacao-refin"},
        {status: 56, selector: "#aguardando-desembolso-refin"},
        {status: 19, selector: "#pendente-correcao-dados-bancarios-refin"},
        {status: 58, selector: "#finalizado-refin"},

    ];
    const statusMappings_Balance = [
        {status: 1000, selector: "#saldo-aprovado"},
        {status: 1001, selector: "#saldo-pendente"},
        {status: 1002, selector: "#saldo-reprovado"},
    ];
    // Retrieve 'type_select_product' from localStorage
    let type_product_cache = localStorage.getItem('type_select_product');

    // Function to set the display of HTML elements to 'none'
    function setElementsDisplay(selector, display) {
        $(selector).remove();
    }

    // Function to load KPI data from an API endpoint and update an HTML element
    function loadKPI(endpoint, elementId) {
        $.get(endpoint, function (data) {
            // Garantindo que o contêiner tenha position: relative para posicionar os spans absolutamente dentro dele
            $(elementId).css('position', 'relative').css('height', '50px'); // Defina a altura conforme necessário

            // Criando HTML com spans posicionados absolutamente
            var sumHtml = "<span style='position: absolute; top: 0; left: 0; font-size: 12px;'>" + data['sum_contract'].toLocaleString('pt-BR', {
                style: 'currency',
                currency: 'BRL'
            }) + "</span>";
            var countHtml = "<span style='position: absolute; top: 0; right: 0; font-size: 32px;'>" + data['count'] + "</span>";

            // Atualizando o elemento HTML com os novos valores estilizados
            $(elementId).html(sumHtml + countHtml);
        });
    }

    // Function to initialize loading by displaying loading HTML in specified elements
    function initializeLoading(elementIds) {
        elementIds.forEach(id => {
            $(id).html(loading);
        });
    }

    // Function to create a comma-separated list of selectors based on mappings
    function structMappings(mappings) {
        return mappings.map(m =>
            `[data-tipo-produto ="${m.selector.replace('#', "")}"]`).join(',');
    }

    // Handle different cases based on URL parameters and product type
    function foreachMappings(mappings) {
        mappings.forEach(m => {
            loadKPI(`/api/kpi/contratos/?tipo_produto=${type_product_cache}&status=${m.status}`, m.selector);
        });
    }

    // Handle different cases based on URL parameters and product type
    if (type_product === null && status === null) {
        initializeLoading(statusMappings_Products.map(m => m.selector));
        statusMappings_Products.forEach(m => {
            loadKPI(`/api/kpi/contratos/?tipo_produto=${m.product}`, m.selector);
        });

        const combine_selectors = structMappings(statusMappings_Port) + ',' + structMappings(statusMappings_FreeMargin) + ',' + structMappings(statusMappings_Refin) + ',' + structMappings(statusMappings_Balance)
        setElementsDisplay(combine_selectors, "none");

    } else if (type_product_cache === "12" || type_product_cache === "17" || type_product_cache === "16") {

        setElementsDisplay(structMappings(statusMappings_Products), "none");
        if (type_product_cache === "12" && (status !== "33" && status !== "1000" && status !== "1001" && status !== "1002")) {

            const combine_exclude_selectors = structMappings(statusMappings_FreeMargin) + ',' + structMappings(statusMappings_Refin) + ',' + structMappings(statusMappings_Balance)
            setElementsDisplay(combine_exclude_selectors, "none");
            initializeLoading(statusMappings_Port.map(m => m.selector));
            foreachMappings(statusMappings_Port)

        } else if (type_product_cache === "16") {

            const combine_exclude_selectors = structMappings(statusMappings_Port) + ',' + structMappings(statusMappings_Refin) + ',' + structMappings(statusMappings_Balance)
            setElementsDisplay(combine_exclude_selectors, "none");
            initializeLoading(statusMappings_FreeMargin.map(m => m.selector));
            foreachMappings(statusMappings_FreeMargin)

        } else if (type_product_cache === "17" && (status !== "33" && status !== "1000" && status !== "1001" && status !== "1002")) {
            const combine_exclude_selectors = structMappings(statusMappings_FreeMargin) + ',' + '[data-tipo-produto="finalizado-port"]' + ',' + structMappings(statusMappings_Balance)
            setElementsDisplay(combine_exclude_selectors, "none");
            initializeLoading(statusMappings_Port.map(m => m.selector));
            foreachMappings(statusMappings_Port)
            initializeLoading(statusMappings_Refin.map(m => m.selector));
            foreachMappings(statusMappings_Refin)
        } else if (type_product_cache === "17" && (status === "33" || status === "1000" || status === "1001" || status === "1002") || type_product_cache === "12" && status === "33") {
            const combine_exclude_selectors = structMappings(statusMappings_Port) + ',' + structMappings(statusMappings_Refin) + ',' + structMappings(statusMappings_FreeMargin)
            setElementsDisplay(combine_exclude_selectors, "none");
            initializeLoading(statusMappings_Balance.map(m => m.selector));
            foreachMappings(statusMappings_Balance)
        }
    } else {
        setElementsDisplay('[data-tipo-produto]', "none");
    }
}
