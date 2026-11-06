INSERT INTO categories (name, description) VALUES
    ('Смартфоны',    'Мобильные телефоны и аксессуары'),
    ('Ноутбуки',     'Портативные компьютеры'),
    ('Планшеты',     'Планшетные ПК'),
    ('Наушники',     'Проводные и беспроводные наушники');

INSERT INTO products (category_id, name, price, stock) VALUES
    (1, 'iPhone 15 Pro',        129990.00, 15),
    (1, 'Samsung Galaxy S24',    89990.00, 22),
    (1, 'Xiaomi Redmi Note 13',  24990.00, 50),
    (2, 'MacBook Air M3',       149990.00, 8),
    (2, 'Lenovo IdeaPad 5',      64990.00, 12),
    (3, 'iPad Air 11',           69990.00, 10),
    (3, 'Samsung Galaxy Tab S9', 79990.00, 7),
    (4, 'Sony WH-1000XM5',       34990.00, 30),
    (4, 'AirPods Pro 2',         24990.00, 40);

INSERT INTO customers (full_name, email, phone) VALUES
    ('Жесткий Тип Типович',   'testtest1@supermail.com',   '+7-666-111-11-11'),
    ('Нежесткий Тип Типович', 'testtest2@supermail.com',  '+7-666-222-11-11'),
    ('Ужасный Паймон Безотчества','testtest3@supermail.com',  '+7-666-111-11-11'),
    ('Честный Тип Типович','testtest4@supermail.com','+7-900-444-55-66');

INSERT INTO orders (customer_id, product_id, quantity) VALUES
    (1, 1, 1),
    (1, 8, 2),
    (2, 4, 1),
    (2, 3, 3),
    (3, 2, 1),
    (3, 9, 2),
    (4, 6, 1),
    (4, 5, 1);