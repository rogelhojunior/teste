from django.core.validators import RegexValidator


class CellphoneValidator(RegexValidator):
    def __init__(self, max_length=11):
        super().__init__(
            regex=rf'^\d{{{max_length}}}$',
            message='Número de telefone inválido. O formato deve ser: 00123456789',
        )
