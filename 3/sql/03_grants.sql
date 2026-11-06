-- Выполняется от имени суперпользователя (ripper666)

CREATE USER shop_user WITH PASSWORD 'shop_user_pass_2024';

GRANT CONNECT ON DATABASE seminar_db TO shop_user;
GRANT USAGE  ON SCHEMA public      TO shop_user;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES IN SCHEMA public TO shop_user;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO shop_user;

-- Права на будущие таблицы/последовательности
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO shop_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO shop_user;