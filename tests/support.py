"""Общие вспомогательные средства для тестов."""

import os
import tempfile
import unittest

REMOTE_VALUES = {
    "package_name": "serde",
    "repository": "https://github.com/serde-rs/serde",
    "repo_mode": "remote",
    "package_version": "1.0.210",
    "output_image": "graph.svg",
    "ascii_tree": "true",
    "max_depth": "3",
}


class TempDirTestCase(unittest.TestCase):
    """Базовый класс: создаёт временный каталог для файлов теста."""

    def setUp(self):
        """Создаёт каталог и регистрирует его удаление."""
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.directory = holder.name

    def path(self, name):
        """Возвращает полный путь к файлу во временном каталоге."""
        return os.path.join(self.directory, name)

    def write(self, name, text):
        """Записывает текст в файл и возвращает его путь."""
        target = self.path(name)
        with open(target, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        return target

    def write_config(self, overrides=None, drop=()):
        """Создаёт CSV-конфигурацию с заменой или удалением параметров."""
        values = dict(REMOTE_VALUES)
        values.update(overrides or {})
        lines = [f"{k},{v}" for k, v in values.items() if k not in drop]
        return self.write("config.csv", "\n".join(lines) + "\n")
