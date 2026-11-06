import json
import os
import sys
from datetime import datetime
from getpass import getpass

import psycopg2
from psycopg2 import sql, errors as pg_errors


LOG_FILE = os.environ.get("LOG_FILE")


def _log(stream, level: str, message: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] [{level}] {message}"
    print(line, file=stream, flush=True)
    if LOG_FILE:
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def log_info(msg: str) -> None:
    _log(sys.stdout, "INFO", msg)


def log_error(msg: str) -> None:
    _log(sys.stderr, "ERROR", msg)


def friendly_db_error(exc: Exception) -> str:
    if isinstance(exc, pg_errors.UniqueViolation):
        return "Запись с таким уникальным значением уже существует."
    if isinstance(exc, pg_errors.ForeignKeyViolation):
        return "Нарушена ссылочная целостность: указан несуществующий связанный объект."
    if isinstance(exc, pg_errors.NotNullViolation):
        return "Обязательное поле не заполнено."
    if isinstance(exc, pg_errors.CheckViolation):
        return "Значение не проходит проверку (например, отрицательная цена или количество)."
    if isinstance(exc, pg_errors.InvalidTextRepresentation):
        return "Неверный формат значения: ожидается число."
    if isinstance(exc, pg_errors.UndefinedTable):
        return "Указанная таблица не найдена."
    if isinstance(exc, pg_errors.UndefinedColumn):
        return "Указанной колонки не существует."
    if isinstance(exc, pg_errors.InsufficientPrivilege):
        return "Недостаточно прав для выполнения операции."
    return "Не удалось выполнить операцию с базой данных. Обратитесь к администратору."


SCHEMA = {
    "categories": ["id", "name", "description"],
    "products":   ["id", "category_id", "name", "price", "stock"],
    "customers":  ["id", "full_name", "email", "phone"],
    "orders":     ["id", "customer_id", "product_id", "quantity", "order_date"],
}


def require_table(name: str) -> str:
    if name not in SCHEMA:
        raise ValueError(f"Таблица '{name}' недоступна. Доступные: {', '.join(SCHEMA)}")
    return name


def require_columns(table: str, columns) -> list:
    require_table(table)
    if isinstance(columns, str):
        columns = [columns]
    for c in columns:
        if c not in SCHEMA[table]:
            raise ValueError(
                f"Колонка '{c}' недоступна в таблице '{table}'. "
                f"Доступные: {', '.join(SCHEMA[table])}"
            )
    return list(columns)


def prompt(msg: str) -> str:
    return input(msg).strip()


def read_int(msg: str) -> int:
    raw = prompt(msg)
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"Ожидалось целое число, получено: {raw!r}")


def read_float(msg: str) -> float:
    raw = prompt(msg)
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        raise ValueError(f"Ожидалось число, получено: {raw!r}")


def show_all(cur, table: str) -> None:
    table = require_table(table)
    log_info(f"Просмотр всех записей из таблицы '{table}'")
    query = sql.SQL("SELECT * FROM {}").format(table)#sql.Identifier(table))
    cur.execute(query)
    _print_result(cur)


def show_filtered_single(cur, table: str) -> None:
    table = require_table(table)
    column = prompt("Колонка для фильтрации: ")
    require_columns(table, column)
    value = prompt(f"Значение для {column}: ")

    log_info(f"Фильтрация таблицы '{table}' по {column} = {value!r}")
    query = sql.SQL("SELECT * FROM {} WHERE {} = %s").format(
        sql.Identifier(table), sql.Identifier(column)
    )
    cur.execute(query, (value,))
    _print_result(cur)


def show_filtered_multi(cur, table: str) -> None:
    table = require_table(table)
    n = read_int("Сколько условий? ")
    if n <= 0:
        raise ValueError("Количество условий должно быть > 0")

    conditions = []
    params = []
    for i in range(n):
        column = prompt(f"  Условие #{i+1} — колонка: ")
        require_columns(table, column)
        value = prompt(f"  Условие #{i+1} — значение: ")
        conditions.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
        params.append(value)

    where = sql.SQL(" AND ").join(conditions)
    query = sql.SQL("SELECT * FROM {} WHERE {}").format(
        sql.Identifier(table), where
    )
    log_info(f"Фильтрация '{table}' по {n} условиям")
    cur.execute(query, params)
    _print_result(cur)


def update_one(cur, table: str) -> None:
    table = require_table(table)
    row_id = read_int("id записи для обновления: ")

    n = read_int("Сколько полей обновить? ")
    if n <= 0:
        raise ValueError("Количество полей должно быть > 0")

    set_parts = []
    params = []
    for i in range(n):
        col = prompt(f"  Поле #{i+1} (имя колонки): ")
        require_columns(table, col)
        if col == "id":
            raise ValueError("Обновлять колонку id запрещено")
        val = prompt(f"  Новое значение для {col}: ")
        set_parts.append(sql.SQL("{} = %s").format(sql.Identifier(col)))
        params.append(val)

    params.append(row_id)
    query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
        sql.Identifier(table), sql.SQL(", ").join(set_parts)
    )
    log_info(f"UPDATE {table} id={row_id} ({n} полей)")
    cur.execute(query, params)
    log_info(f"Обновлено строк: {cur.rowcount}")


def update_many(cur, table: str) -> None:
    table = require_table(table)

    filter_col = prompt("Колонка для фильтрации (WHERE ... IN): ")
    require_columns(table, filter_col)

    target_col = prompt("Колонка для обновления: ")
    require_columns(table, target_col)
    if target_col == "id":
        raise ValueError("Обновлять колонку id запрещено")

    new_value = prompt(f"Новое значение для {target_col}: ")

    raw_values = prompt("Значения для IN через запятую: ")
    values = [v.strip() for v in raw_values.split(",") if v.strip()]
    if not values:
        raise ValueError("Не указано ни одного значения для IN")

    placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(values))
    query = sql.SQL("UPDATE {} SET {} = %s WHERE {} IN ({})").format(
        sql.Identifier(table),
        sql.Identifier(target_col),
        sql.Identifier(filter_col),
        placeholders,
    )
    params = [new_value] + values
    log_info(f"UPDATE {table} SET {target_col}={new_value!r} WHERE {filter_col} IN {values}")
    cur.execute(query, params)
    log_info(f"Обновлено строк: {cur.rowcount}")


def insert_one(cur, table: str) -> None:
    table = require_table(table)
    cols = require_columns(table, prompt_cols_except_id(table))

    values = []
    for c in cols:
        values.append(prompt(f"  Значение для {c}: "))

    placeholders = sql.SQL(", ").join([sql.Placeholder()] * len(cols))
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, cols)),
        placeholders,
    )
    log_info(f"INSERT INTO {table} ({', '.join(cols)})")
    cur.execute(query, values)
    log_info(f"Вставлено строк: {cur.rowcount}")


def insert_into_two_related(cur) -> None:
    log_info("Вставка в две связанные таблицы: categories -> products")

    cat_name = prompt("Название новой категории: ")
    cat_desc = prompt("Описание категории: ")

    prod_name  = prompt("Название товара: ")
    prod_price = read_float("Цена товара: ")
    prod_stock = read_int("Количество на складе: ")

    cur.execute(
        sql.SQL("INSERT INTO categories (name, description) VALUES (%s, %s) RETURNING id"),
        (cat_name, cat_desc),
    )
    new_cat_id = cur.fetchone()[0]

    cur.execute(
        sql.SQL(
            "INSERT INTO products (category_id, name, price, stock) "
            "VALUES (%s, %s, %s, %s)"
        ),
        (new_cat_id, prod_name, prod_price, prod_stock),
    )
    log_info(f"Создана категория id={new_cat_id} и товар '{prod_name}'")


def insert_many_single(cur, table: str) -> None:
    table = require_table(table)
    cols = require_columns(table, prompt_cols_except_id(table))

    n = read_int("Сколько строк вставить? ")
    if n <= 0:
        raise ValueError("Количество строк должно быть > 0")

    rows = []
    for i in range(n):
        row = []
        for c in cols:
            row.append(prompt(f"  Строка #{i+1}, {c}: "))
        rows.append(row)

    placeholders_one = sql.SQL("(") + sql.SQL(", ").join(
        [sql.Placeholder()] * len(cols)
    ) + sql.SQL(")")
    placeholders = sql.SQL(", ").join([placeholders_one] * n)

    query = sql.SQL("INSERT INTO {} ({}) VALUES {}").format(
        sql.Identifier(table),
        sql.SQL(", ").join(map(sql.Identifier, cols)),
        placeholders,
    )
    flat_params = [v for row in rows for v in row]
    log_info(f"INSERT INTO {table} — {n} строк")
    cur.execute(query, flat_params)
    log_info(f"Вставлено строк: {cur.rowcount}")


def insert_many_related(cur) -> None:
    log_info("Вставка в несколько связанных таблиц: customers -> orders (много)")

    full_name = prompt("ФИО нового клиента: ")
    email     = prompt("Email клиента: ")
    phone     = prompt("Телефон клиента: ")

    cur.execute(
        sql.SQL(
            "INSERT INTO customers (full_name, email, phone) "
            "VALUES (%s, %s, %s) RETURNING id"
        ),
        (full_name, email, phone),
    )
    customer_id = cur.fetchone()[0]
    log_info(f"Создан клиент id={customer_id}")

    n = read_int("Сколько заказов создать? ")
    if n <= 0:
        raise ValueError("Количество заказов должно быть > 0")

    rows = []
    for i in range(n):
        pid = read_int(f"  Заказ #{i+1} — product_id: ")
        qty = read_int(f"  Заказ #{i+1} — quantity: ")
        rows.append((customer_id, pid, qty))

    placeholders_one = sql.SQL("(%s, %s, %s)")
    placeholders = sql.SQL(", ").join([placeholders_one] * n)
    query = sql.SQL(
        "INSERT INTO orders (customer_id, product_id, quantity) VALUES {}"
    ).format(placeholders)

    flat = [v for r in rows for v in r]
    cur.execute(query, flat)
    log_info(f"Вставлено заказов: {cur.rowcount}")


def prompt_cols_except_id(table: str) -> list:
    raw = prompt("Колонки через запятую (без id): ")
    cols = [c.strip() for c in raw.split(",") if c.strip()]
    if not cols:
        raise ValueError("Не указано ни одной колонки")
    return cols


def _print_result(cur) -> None:
    rows = cur.fetchall()
    if not rows:
        log_info("(пусто)")
        return
    colnames = [d[0] for d in cur.description]
    log_info(" | ".join(colnames))
    log_info("-" * 60)
    for r in rows:
        log_info(" | ".join("" if v is None else str(v) for v in r))
    log_info(f"Всего строк: {len(rows)}")


MENU = """
========= МЕНЮ =========
1. Показать всё из таблицы
2. Показать с фильтром по одной колонке
3. Показать с фильтром по нескольким колонкам (AND)
4. Обновить одну запись (несколько полей)
5. Обновить несколько записей (общее значение по IN)
6. Вставить одну строку
7. Вставить строку в две связанные таблицы (categories + products)
8. Вставить несколько строк в одну таблицу
9. Вставить несколько строк в связанные таблицы (customers + orders)
0. Выход
"""


def choose_table() -> str:
    log_info("Доступные таблицы: " + ", ".join(SCHEMA.keys()))
    return prompt("Таблица: ")


def main() -> int:
    with open("config.json", "r", encoding="utf-8") as f:
        cfg = json.load(f)

    cfg["host"] = os.environ.get("DB_HOST", cfg["host"])
    cfg["port"] = int(os.environ.get("DB_PORT", cfg["port"]))
    cfg["dbname"] = os.environ.get("DB_NAME", cfg["dbname"])
    cfg["connect_timeout"] = int(
        os.environ.get("DB_CONNECT_TIMEOUT", cfg.get("connect_timeout", 5))
    )

    log_info("Введите данные для подключения к БД.")
    user = input("Логин: ").strip()
    password = getpass("Пароль: ")

    conn = None
    try:
        conn = psycopg2.connect(
            host=cfg["host"],
            port=cfg["port"],
            dbname=cfg["dbname"],
            user=user,
            password=password,
            connect_timeout=cfg["connect_timeout"],
        )
        conn.autocommit = False
        log_info(f"Успешное подключение к БД '{cfg['dbname']}' на {cfg['host']}:{cfg['port']}")
    except psycopg2.OperationalError as exc:
        log_error(f"Не удалось подключиться к БД. Техническая причина: {exc}")
        msg = str(exc).lower()
        if "password authentication failed" in msg:
            log_error("Причина: неверный логин или пароль.")
        elif "does not exist" in msg:
            log_error("Причина: указанного пользователя не существует.")
        elif "could not connect" in msg or "connection refused" in msg:
            log_error("Причина: сервер БД недоступен по указанному адресу.")
        elif "timeout" in msg or "timed out" in msg:
            log_error("Причина: истекло время ожидания подключения к БД.")
        else:
            log_error("Причина: не удалось подключиться к базе данных.")
        return 1
    except Exception as exc:
        log_error(f"Не удалось подключиться к БД. Техническая причина: {exc}")
        log_error("Причина: непредвиденная ошибка подключения.")
        return 1

    cur = conn.cursor()
    try:
        while True:
            print(MENU)
            choice = prompt("Выбор: ")

            try:
                if choice == "1":
                    show_all(cur, choose_table())
                elif choice == "2":
                    show_filtered_single(cur, choose_table())
                elif choice == "3":
                    show_filtered_multi(cur, choose_table())
                elif choice == "4":
                    update_one(cur, choose_table())
                elif choice == "5":
                    update_many(cur, choose_table())
                elif choice == "6":
                    insert_one(cur, choose_table())
                elif choice == "7":
                    insert_into_two_related(cur)
                elif choice == "8":
                    insert_many_single(cur, choose_table())
                elif choice == "9":
                    insert_many_related(cur)
                elif choice == "0":
                    log_info("Выход.")
                    break
                else:
                    log_error("Некорректный пункт меню.")
                    continue

                conn.commit()
            except ValueError as ve:
                conn.rollback()
                log_error(f"Ошибка ввода: {ve}")
            except pg_errors.Error as dbe:
                conn.rollback()
                log_error(f"Ошибка БД: {friendly_db_error(dbe)}")
                log_error(f"Техническая причина: {type(dbe).__name__}: {dbe}")
            except Exception as exc:
                conn.rollback()
                log_error(f"Непредвиденная ошибка: {friendly_db_error(exc)}")
                log_error(f"Техническая причина: {type(exc).__name__}: {exc}")
    finally:
        cur.close()
        conn.close()
        log_info("Соединение с БД закрыто.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
