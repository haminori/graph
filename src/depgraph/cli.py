"""Интерфейс командной строки инструмента визуализации зависимостей."""

import argparse
import sys

from depgraph.config import format_config, load_config
from depgraph.errors import ConfigError

DEFAULT_CONFIG = "config.csv"
EXIT_OK = 0
EXIT_CONFIG_ERROR = 1


def build_parser():
    """Создаёт разборщик аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="depgraph",
        description="Визуализация графа зависимостей пакетов Cargo.",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=DEFAULT_CONFIG,
        help="путь к CSV-файлу конфигурации (по умолчанию config.csv)",
    )
    return parser


def report_errors(error):
    """Печатает все найденные ошибки конфигурации в stderr."""
    print("Ошибка конфигурации:", file=sys.stderr)
    for message in error.messages:
        print(f"  - {message}", file=sys.stderr)


def main(argv=None):
    """Запускает приложение и возвращает код завершения процесса.

    Args:
        argv: список аргументов; по умолчанию берётся sys.argv.
    """
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except ConfigError as error:
        report_errors(error)
        return EXIT_CONFIG_ERROR
    print(format_config(config))
    return EXIT_OK
