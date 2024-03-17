from message_bus.commands import EventCommands
from message_bus.consumers.face_match_handler import handle_face_match_response


class EventProcessorMapping:
    def __init__(self):
        # Aqui, definimos o mapeamento como um atributo da instância.
        self.mapping = {
            EventCommands.SEND_FACE_MATCHED_RESPONSE.value: handle_face_match_response
        }

    def get_mapping(self):
        """
        Retorna o mapeamento de nomes de eventos para processadores de eventos.
        """
        return self.mapping
