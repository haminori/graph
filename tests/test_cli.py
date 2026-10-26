"""Тесты интерфейса командной строки."""

import contextlib
import io

from depgraph.cli import EXIT_CONFIG_ERROR, EXIT_OK, main
from tests.support import TempDirTestCase


def run_main(args):
    """Запускает main и возвращает (код, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


class CliTests(TempDirTestCase):
    """Проверка кодов возврата и вывода приложения."""

    def test_prints_all_parameters(self):
        """При успехе все параметры печатаются парами ключ = значение."""
        code, out, _ = run_main(["--config", self.write_config()])
        self.assertEqual(code, EXIT_OK)
        self.assertIn("repository = https://github.com/serde-rs/serde", out)
        self.assertIn("max_depth = 3", out)

    def test_error_goes_to_stderr(self):
        """При ошибке код ненулевой, сообщение идёт в stderr."""
        path = self.write_config({"max_depth": "zero"})
        code, out, err = run_main(["-c", path])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertEqual(out, "")
        self.assertIn("Ошибка конфигурации", err)

    def test_missing_config_file(self):
        """Отсутствующий файл конфигурации даёт понятную ошибку."""
        code, _, err = run_main(["-c", self.path("absent.csv")])
        self.assertEqual(code, EXIT_CONFIG_ERROR)
        self.assertIn("не найден", err)
