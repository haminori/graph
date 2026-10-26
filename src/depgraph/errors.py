"""Исключения приложения."""


class ConfigError(Exception):
    """Ошибка конфигурации; хранит список понятных сообщений."""

    def __init__(self, messages):
        """Сохраняет сообщения об ошибках.

        Args:
            messages: список строк с описанием найденных проблем.
        """
        super().__init__("; ".join(messages))
        self.messages = list(messages)
