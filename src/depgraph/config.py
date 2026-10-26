"""Чтение и проверка конфигурационного файла в формате CSV.

Файл состоит из строк ``параметр,значение``. Первая строка-заголовок
``parameter,value`` необязательна.
"""

import csv
import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from depgraph.errors import ConfigError

KEY_PACKAGE = "package_name"
KEY_REPOSITORY = "repository"
KEY_MODE = "repo_mode"
KEY_VERSION = "package_version"
KEY_OUTPUT = "output_image"
KEY_ASCII = "ascii_tree"
KEY_DEPTH = "max_depth"

PARAMETER_ORDER = (
    KEY_PACKAGE,
    KEY_REPOSITORY,
    KEY_MODE,
    KEY_VERSION,
    KEY_OUTPUT,
    KEY_ASCII,
    KEY_DEPTH,
)

HEADER_ROW = ("parameter", "value")
PAIR_SIZE = 2
MODE_REMOTE = "remote"
MODE_TEST = "test"
MODES = (MODE_REMOTE, MODE_TEST)
TRUE_VALUES = frozenset({"true", "yes", "1", "on"})
FALSE_VALUES = frozenset({"false", "no", "0", "off"})
URL_SCHEMES = frozenset({"http", "https"})
IMAGE_SUFFIX = ".svg"
MIN_DEPTH = 1
MAX_DEPTH = 100
MAX_NAME_LENGTH = 64

CRATE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]*")
TEST_NAME = re.compile(r"[A-Z]+")
DIGITS = re.compile(r"[0-9]+")
BAD_FILE_CHARS = re.compile(r'[<>:"|?*\x00-\x1f]')
SEMVER_NUMBER = r"(0|[1-9][0-9]*)"
SEMVER = re.compile(
    rf"{SEMVER_NUMBER}\.{SEMVER_NUMBER}\.{SEMVER_NUMBER}"
    r"(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?"
)


@dataclass(frozen=True)
class Config:
    """Проверенные параметры, заданные пользователем."""

    package_name: str
    repository: str
    repo_mode: str
    package_version: str
    output_image: str
    ascii_tree: bool
    max_depth: int


def check_file(path):
    """Проверяет, что путь указывает на существующий читаемый файл."""
    if not os.path.exists(path):
        raise ConfigError([f"файл конфигурации '{path}' не найден"])
    if not os.path.isfile(path):
        raise ConfigError([f"'{path}' не является файлом"])
    if not os.access(path, os.R_OK):
        raise ConfigError([f"нет прав на чтение файла '{path}'"])


def is_blank(row):
    """Возвращает True, если все ячейки строки пусты."""
    return not any(cell.strip() for cell in row)


def read_rows(path):
    """Читает CSV и возвращает пары (номер строки, ячейки) без пустых."""
    check_file(path)
    try:
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, strict=True)
            rows = [(reader.line_num, row) for row in reader]
    except UnicodeDecodeError:
        raise ConfigError([f"файл '{path}' не в кодировке UTF-8"]) from None
    except csv.Error as error:
        raise ConfigError([f"некорректный CSV в '{path}': {error}"]) from None
    except OSError as error:
        raise ConfigError([f"ошибка чтения '{path}': {error}"]) from None
    return [(line, row) for line, row in rows if not is_blank(row)]


def strip_header(rows):
    """Отбрасывает необязательную строку-заголовок parameter,value."""
    (_, first), *rest = rows
    normalized = tuple(cell.strip().lower() for cell in first)
    return rest if normalized == HEADER_ROW else rows


def add_pair(pairs, line, row):
    """Добавляет пару ключ-значение; возвращает текст ошибки или None."""
    if len(row) != PAIR_SIZE:
        return (
            f"строка {line}: ожидалось столбцов: {PAIR_SIZE}, "
            f"получено: {len(row)}"
        )
    key, value = (cell.strip() for cell in row)
    if key not in PARAMETER_ORDER:
        return f"строка {line}: неизвестный параметр '{key}'"
    if key in pairs:
        return f"строка {line}: параметр '{key}' указан повторно"
    pairs[key] = value
    return None


def parse_pairs(rows):
    """Преобразует строки CSV в словарь; возвращает (словарь, ошибки)."""
    pairs = {}
    errors = []
    for line, row in strip_header(rows):
        problem = add_pair(pairs, line, row)
        if problem:
            errors.append(problem)
    return pairs, errors


def parse_bool(value):
    """Разбирает логическое значение true/false (yes/no, 1/0, on/off)."""
    lowered = value.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise ValueError(f"ожидалось true или false, получено '{value}'")


def parse_depth(value):
    """Разбирает максимальную глубину анализа зависимостей."""
    in_range = DIGITS.fullmatch(value) and (
        MIN_DEPTH <= int(value) <= MAX_DEPTH
    )
    if not in_range:
        raise ValueError(
            f"ожидалось целое число от {MIN_DEPTH} до {MAX_DEPTH}, "
            f"получено '{value}'"
        )
    return int(value)


def parse_mode(value):
    """Разбирает режим работы с репозиторием: remote или test."""
    lowered = value.lower()
    if lowered not in MODES:
        raise ValueError(
            f"допустимые режимы: {', '.join(MODES)}; получено '{value}'"
        )
    return lowered


def parse_version(value):
    """Проверяет версию пакета по правилам SemVer (как в Cargo)."""
    if not SEMVER.fullmatch(value):
        raise ValueError(
            f"ожидалась версия вида MAJOR.MINOR.PATCH, получено '{value}'"
        )
    return value


def parse_output(value):
    """Проверяет имя SVG-файла для изображения графа."""
    name = os.path.basename(value)
    if name.lower() in ("", IMAGE_SUFFIX) or not name.lower().endswith(
        IMAGE_SUFFIX
    ):
        raise ValueError(f"имя файла должно оканчиваться на {IMAGE_SUFFIX}")
    if BAD_FILE_CHARS.search(name):
        raise ValueError(f"недопустимые символы в имени файла '{name}'")
    directory = os.path.dirname(value)
    if directory and not os.path.isdir(directory):
        raise ValueError(f"каталог '{directory}' не существует")
    return value


def parse_package(value, mode):
    """Проверяет имя пакета с учётом режима работы."""
    if mode == MODE_TEST:
        if not TEST_NAME.fullmatch(value):
            raise ValueError(
                f"в режиме test имя пакета - заглавные латинские буквы, "
                f"получено '{value}'"
            )
        return value
    if not CRATE_NAME.fullmatch(value) or len(value) > MAX_NAME_LENGTH:
        raise ValueError(
            f"имя крейта: латинская буква, затем буквы, цифры, '-' или '_', "
            f"не длиннее {MAX_NAME_LENGTH} символов; получено '{value}'"
        )
    return value


def has_valid_port(parts):
    """Возвращает True, если порт в разобранном URL корректен."""
    try:
        return parts.port is None or bool(parts.port)
    except ValueError:
        return False


def check_url(value):
    """Проверяет, что значение - корректный http(s) URL."""
    try:
        parts = urlparse(value)
    except ValueError:
        raise ValueError(f"некорректный URL '{value}'") from None
    has_space = any(char.isspace() for char in value)
    valid = parts.hostname and not has_space and has_valid_port(parts)
    if parts.scheme not in URL_SCHEMES or not valid:
        raise ValueError(
            f"ожидался URL вида http(s)://хост/путь, получено '{value}'"
        )
    return value


def check_test_repo_path(value):
    """Проверяет, что значение - путь к существующему читаемому файлу."""
    if urlparse(value).scheme in URL_SCHEMES:
        raise ValueError("в режиме test нужен путь к файлу, а не URL")
    if not os.path.isfile(value):
        raise ValueError(f"файл тестового репозитория '{value}' не найден")
    if not os.access(value, os.R_OK):
        raise ValueError(f"нет прав на чтение файла '{value}'")
    return value


def parse_repository(value, mode):
    """Проверяет URL или путь к файлу в зависимости от режима."""
    if mode == MODE_TEST:
        return check_test_repo_path(value)
    if mode == MODE_REMOTE:
        return check_url(value)
    return value


SIMPLE_PARSERS = {
    KEY_MODE: parse_mode,
    KEY_VERSION: parse_version,
    KEY_OUTPUT: parse_output,
    KEY_ASCII: parse_bool,
    KEY_DEPTH: parse_depth,
}


class Validator:
    """Накапливает разобранные значения параметров и ошибки проверки."""

    def __init__(self, pairs):
        """Запоминает исходные строковые значения параметров."""
        self.pairs = pairs
        self.values = {}
        self.errors = []

    def report_missing(self):
        """Добавляет ошибки для обязательных, но не заданных параметров."""
        for key in PARAMETER_ORDER:
            if key not in self.pairs:
                self.errors.append(f"параметр '{key}' не задан")

    def parse(self, key, parser, *extra):
        """Разбирает один параметр, при ошибке сохраняет сообщение."""
        raw = self.pairs.get(key)
        if raw is None:
            return
        try:
            if not raw:
                raise ValueError("значение не задано")
            self.values[key] = parser(raw, *extra)
        except ValueError as error:
            self.errors.append(f"параметр '{key}': {error}")


def build_config(pairs):
    """Проверяет все параметры и возвращает Config либо бросает ошибку."""
    checker = Validator(pairs)
    checker.report_missing()
    for key, parser in SIMPLE_PARSERS.items():
        checker.parse(key, parser)
    mode = checker.values.get(KEY_MODE)
    checker.parse(KEY_PACKAGE, parse_package, mode)
    checker.parse(KEY_REPOSITORY, parse_repository, mode)
    if checker.errors:
        raise ConfigError(checker.errors)
    return Config(**checker.values)


def load_config(path):
    """Читает CSV-файл конфигурации и возвращает проверенный Config."""
    rows = read_rows(path)
    if not rows:
        raise ConfigError([f"файл '{path}' пуст"])
    pairs, errors = parse_pairs(rows)
    if errors:
        raise ConfigError(errors)
    return build_config(pairs)


def format_value(value):
    """Преобразует значение параметра в строку для вывода."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def format_config(config):
    """Возвращает параметры в виде строк формата 'ключ = значение'."""
    return "\n".join(
        f"{key} = {format_value(getattr(config, key))}"
        for key in PARAMETER_ORDER
    )
