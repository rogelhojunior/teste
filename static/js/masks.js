$(document).ready(function() {
    // Aplica a máscara de moeda no input de valor_segurado
    $('#id_valor_segurado').mask('#.##0,00', {reverse: true});
    $('#id_valor_pago_cliente').mask('#.##0,00', {reverse: true});
});
