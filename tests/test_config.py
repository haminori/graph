"""Тесты чтения и проверки конфигурации."""

import os

from depgraph.config import format_config, load_config
from depgraph.errors import ConfigError
from tests.support import REMOTE_VALUES, TempDirTestCase

EXPECTED_ERRORS = 2


class ValidConfigTests(TempDirTestCase):
    """Проверка корректных конфигураций."""

    def test_remote_config(self):
        """Корректный файл режима remote разбирается полностью."""
        config = load_config(self.write_config())
        self.assertEqual(config.package_name, "serde")
        self.assertEqual(config.max_depth, 3)
        self.assertTrue(config.ascii_tree)

    def test_test_mode_config(self):
        """В режиме test требуется существующий файл и имя из букв A-Z."""
        repo = self.write("repo.txt", "A: B\nB:\n")
        overrides = {
            "repo_mode": "test",
            "package_name": "A",
            "repository": repo,
        }
        config = load_config(self.write_config(overrides))
        self.assertEqual(config.repo_mode, "test")

    def test_header_bom_and_blank_lines(self):
        """Заголовок, BOM и пустые строки допускаются."""
        body = "\n".join(f"{k},{v}" for k, v in REMOTE_VALUES.items())
        text = "\ufeffparameter,value\n\n" + body + "\n\n"
        config = load_config(self.write("bom.csv", text))
        self.assertEqual(config.package_version, "1.0.210")

    def test_format_config(self):
        """Вывод содержит все параметры в формате ключ = значение."""
        output = format_config(load_config(self.write_config()))
        self.assertIn("package_name = serde", output)
        self.assertIn("ascii_tree = true", output)
        self.assertEqual(len(output.splitlines()), len(REMOTE_VALUES))


class FileErrorTests(TempDirTestCase):
    """Ошибки на уровне файла конфигурации."""

    def assert_error(self, path, fragment):
        """Проверяет, что загрузка падает с сообщением с фрагментом."""
        with self.assertRaises(ConfigError) as context:
            load_config(path)
        self.assertIn(fragment, " ".join(context.exception.messages))

    def test_missing_file(self):
        """Несуществующий файл."""
        self.assert_error(self.path("nope.csv"), "не найден")

    def test_directory_instead_of_file(self):
        """Вместо файла указан каталог."""
        self.assert_error(self.directory, "не является файлом")

    def test_empty_file(self):
        """Пустой файл."""
        self.assert_error(self.write("e.csv", ""), "пуст")

    def test_not_utf8(self):
        """Файл не в кодировке UTF-8."""
        target = self.path("bin.csv")
        with open(target, "wb") as handle:
            handle.write(b"\xff\xfe\x00\x80")
        self.assert_error(target, "UTF-8")

    def test_wrong_column_count(self):
        """Строка с неверным числом столбцов."""
        self.assert_error(self.write("c.csv", "a,b,c\n"), "столбцов")

    def test_unknown_and_duplicate(self):
        """Неизвестный и повторяющийся параметры."""
        base = self.write_config()
        with open(base, "a", encoding="utf-8") as handle:
            handle.write("color,red\nmax_depth,4\n")
        self.assert_error(base, "неизвестный параметр")
        self.assert_error(base, "указан повторно")

    def test_missing_parameter(self):
        """Не заданы обязательные параметры."""
        path = self.write_config(drop=("max_depth", "repo_mode"))
        self.assert_error(path, "параметр 'max_depth' не задан")
        self.assert_error(path, "параметр 'repo_mode' не задан")


class ValueErrorTests(TempDirTestCase):
    """Ошибки в значениях каждого параметра."""

    BAD_VALUES = {
        "package_name": ["", "1serde", "se rde", "a" * 65],
        "repository": ["github", "ftp://host/x", "https://", "http://a b"],
        "repo_mode": ["local", "REMOTEX"],
        "package_version": ["1.0", "01.0.0", "v1.0.0", "1.0.0."],
        "output_image": ["graph.png", ".svg", "dir/none/g.svg", "a?.svg"],
        "ascii_tree": ["maybe", "2"],
        "max_depth": ["-1", "0", "3.5", "abc", "101"],
    }

    def test_bad_values(self):
        """Каждое неверное значение приводит к ошибке своего параметра."""
        for key, values in self.BAD_VALUES.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    path = self.write_config({key: value})
                    with self.assertRaises(ConfigError) as context:
                        load_config(path)
                    joined = " ".join(context.exception.messages)
                    self.assertIn(f"параметр '{key}'", joined)

    def test_all_errors_reported_together(self):
        """Несколько ошибок выводятся одновременно."""
        path = self.write_config({"max_depth": "x", "repo_mode": "bad"})
        with self.assertRaises(ConfigError) as context:
            load_config(path)
        self.assertEqual(len(context.exception.messages), EXPECTED_ERRORS)

    def test_test_mode_rules(self):
        """Режим test: нужен путь к файлу и имя из заглавных букв."""
        cases = [
            {"package_name": "A", "repository": self.path("none.txt")},
            {"package_name": "A", "repository": "https://example.com/r"},
            {"package_name": "abc", "repository": self.write("r.txt", "A:")},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                path = self.write_config({"repo_mode": "test", **extra})
                with self.assertRaises(ConfigError):
                    load_config(path)

    def test_valid_output_with_directory(self):
        """Имя файла с существующим каталогом допустимо."""
        target = os.path.join(self.directory, "g.svg")
        config = load_config(self.write_config({"output_image": target}))
        self.assertEqual(config.output_image, target)
