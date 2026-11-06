from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser


class SafeJSONParser(JSONParser):
    """JSON с вложенностью в сотни тысяч уровней не должен приводить к ошибке 500 на открытых формах"""

    def parse(self, stream, media_type=None, parser_context=None):
        try:
            return super().parse(stream, media_type, parser_context)
        except RecursionError:
            raise ParseError('Слишком большая вложенность данных.')
