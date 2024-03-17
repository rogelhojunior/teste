class StatusAndProducts:
    """
    Class to manage the creation of product and status entries.
    """

    ICON_HEART = 'fa fa-heart'
    ICON_STAR = 'fa fa-star'
    ICON_CHECK = 'fa fa-check'
    ICON_CALENDAR = 'fa fa-calendar'
    ICON_USER = 'fa fa-user'
    ICON_ENVELOPE = 'fa fa-envelope'
    ICON_LOCK = 'fa fa-lock'
    ICON_SEARCH = 'fa fa-search'
    ICON_HOME = 'fa fa-home'
    ICON_PHONE = 'fa fa-phone'
    ICON_TASK = 'fa fa-tasks'
    ICON_BELL = 'fa fa-bell'
    ICON_CLOCK = 'fas fa-clock'
    ICON_EXCLAMATION = 'fas fa-exclamation-circle'

    def __init__(self):
        """Initialize the StatusAndProducts class."""
        self.products = self._assemble_products()
        self.statuses = self._assemble_status()

    def _create_entry(self, type_name, color, id_name, number, icon):
        """
        Creates a dictionary entry for a product or status type.
        """
        return {
            'type_name': type_name,
            'color': color,
            'number': number,
            'id_name': id_name,
            'icon': icon,
        }

    def _create_loan_products(self):
        """Creates loan product entries."""
        return [
            self._create_entry(
                'MARGEM LIVRE',
                'gray_margem_livre',
                'margem-livre',
                '16',
                self.ICON_CLOCK,
            ),
            self._create_entry(
                'PORT + REFIN',
                'gray_port_refin',
                'portabilidade-refinanciamento',
                '17',
                self.ICON_ENVELOPE,
            ),
            self._create_entry(
                'PORTABILIDADE', 'gray_port', 'portabilidade', '12', self.ICON_HOME
            ),
        ]

    def _create_card_products(self):
        """Creates card product entries."""
        return [
            self._create_entry(
                'CARTÃO BENEFICIO', 'blue', 'cartao-beneficio', '7', self.ICON_HEART
            ),
            self._create_entry(
                'CARTÃO CONSIGNADO',
                'slate-blue3',
                'cartao-consignado',
                '15',
                self.ICON_LOCK,
            ),
            self._create_entry(
                'SAQUE COMPLEMENTAR',
                'dark-slate-blue',
                'saque-complementar',
                '14',
                self.ICON_SEARCH,
            ),
        ]

    def _create_status_free_margin(self):
        """Creates status entries for free margin."""
        return [
            self._create_entry(
                'AGUARDANDO IN100 DIGITACAO',
                'blue',
                'aguardando-in100-margem-livre',
                '42',
                self.ICON_SEARCH,
            ),
            self._create_entry(
                'INT AGUARDANDO AVERBAÇÃO',
                'yellow',
                'aguardando-averbacao-margem-livre',
                '37',
                self.ICON_BELL,
            ),
            self._create_entry(
                'AGUARDANDO DESEMBOLSO',
                'orange',
                'aguardando-desembolso-margem-livre',
                '13',
                self.ICON_ENVELOPE,
            ),
            self._create_entry(
                'CORREÇÃO DADOS BANCÁRIOS',
                'purple',
                'pendente-correcao-dados-bancarios-margem-livre',
                '19',
                self.ICON_PHONE,
            ),
            self._create_entry(
                'REPROVADOS',
                'red',
                'reprovado-margem-livre',
                '41',
                self.ICON_EXCLAMATION,
            ),
            self._create_entry(
                'FINALIZADO',
                'success',
                'finalizado-margem-livre',
                '38',
                self.ICON_STAR,
            ),
        ]

    def _create_status_port(self):
        """Creates status entries for portability."""
        return [
            self._create_entry(
                'AGUARDANDO IN100 DIGITACAO',
                'blue',
                'aguardando-in100-digitacao-port',
                '42',
                self.ICON_HOME,
            ),
            self._create_entry(
                'AGUARDANDO IN100 RECALCULO',
                'dark',
                'aguardando-in100-recalculo-port',
                '43',
                self.ICON_ENVELOPE,
            ),
            self._create_entry(
                'IN100 RETORNADA RECALCULO',
                'trodi',
                'in100-retornada-recalculo-port',
                '44',
                self.ICON_PHONE,
            ),
            self._create_entry(
                'SALDOS RETORNADOS',
                'purple',
                'saldo-retornado-port',
                '33',
                self.ICON_BELL,
            ),
            self._create_entry(
                'AGUARD AVERBACAO',
                'orange',
                'aguardando-averbacao-port',
                '37',
                self.ICON_CLOCK,
            ),
            self._create_entry(
                'AGUARD PAGAMENTO',
                'yellow',
                'aguardando-pagamento-port',
                '34',
                self.ICON_CALENDAR,
            ),
            self._create_entry(
                'REPROVADOS', 'red', 'reprovado-port', '41', self.ICON_EXCLAMATION
            ),
            self._create_entry(
                'PORT FINALIZADO',
                'success',
                'finalizado-port',
                '38',
                self.ICON_STAR,
            ),
        ]

    def _create_status_refin(self):
        """Creates status entries for refinancing."""
        return [
            self._create_entry(
                'AGUARDANDO AVERBACAO REFIN',
                'yellow',
                'aguardando-averbacao-refin',
                '55',
                self.ICON_HOME,
            ),
            self._create_entry(
                'AGUARDANDO DESEMBOLSO REFIN',
                'orange',
                'aguardando-desembolso-refin',
                '56',
                self.ICON_CALENDAR,
            ),
            self._create_entry(
                'CORREÇÃO DADOS BANCÁRIOS',
                'purple',
                'pendente-correcao-dados-bancarios-refin',
                '19',
                self.ICON_EXCLAMATION,
            ),
            self._create_entry(
                'REFIN FINALIZADO',
                'success',
                'finalizado-refin',
                '58',
                self.ICON_STAR,
            ),
        ]

    def _create_status_balance(self):
        """Creates status entries for refinancing."""
        return [
            self._create_entry(
                'SALDO APROVADO',
                'success',
                'saldo-aprovado',
                '1000',
                self.ICON_CALENDAR,
            ),
            self._create_entry(
                'SALDO PENDENTE',
                'yellow',
                'saldo-pendente',
                '1001',
                self.ICON_HOME,
            ),
            self._create_entry(
                'SALDO REPROVADO',
                'red',
                'saldo-reprovado',
                '1002',
                self.ICON_EXCLAMATION,
            ),
        ]

    def _assemble_products(self):
        """Assembles all product entries."""
        return self._create_loan_products() + self._create_card_products()

    def _assemble_status(self):
        """Assembles all status entries."""
        return (
            self._create_status_free_margin()
            + self._create_status_port()
            + self._create_status_refin()
            + self._create_status_balance()
        )
