DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS users;

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    amount DOUBLE NOT NULL,
    created_at TIMESTAMP NOT NULL
);

CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL
);

INSERT INTO customers (id, name, email, created_at) VALUES
    (1, 'Ava Chen', 'ava.chen@example.com', CURRENT_TIMESTAMP - INTERVAL '10 days'),
    (2, 'Liam Patel', 'liam.patel@example.com', CURRENT_TIMESTAMP - INTERVAL '20 days'),
    (3, 'Sofia Ramirez', 'sofia.ramirez@example.com', CURRENT_TIMESTAMP - INTERVAL '5 days'),
    (4, 'Noah Kim', 'noah.kim@example.com', CURRENT_TIMESTAMP - INTERVAL '2 days'),
    (5, 'Mia Johnson', 'mia.johnson@example.com', CURRENT_TIMESTAMP - INTERVAL '15 days');

INSERT INTO orders (id, customer_id, amount, created_at) VALUES
    (101, 1, 320.50, CURRENT_TIMESTAMP - INTERVAL '9 days'),
    (102, 2, 89.99, CURRENT_TIMESTAMP - INTERVAL '12 days'),
    (103, 3, 560.00, CURRENT_TIMESTAMP - INTERVAL '4 days'),
    (104, 4, 42.75, CURRENT_TIMESTAMP - INTERVAL '1 days'),
    (105, 5, 230.10, CURRENT_TIMESTAMP - INTERVAL '13 days'),
    (106, 1, 145.20, CURRENT_TIMESTAMP - INTERVAL '3 days'),
    (107, 3, 980.00, CURRENT_TIMESTAMP - INTERVAL '6 days'),
    (108, 2, 75.00, CURRENT_TIMESTAMP - INTERVAL '8 days'),
    (109, 4, 410.30, CURRENT_TIMESTAMP - INTERVAL '2 days'),
    (110, 5, 125.00, CURRENT_TIMESTAMP - INTERVAL '7 days');

INSERT INTO users (id, username, status, created_at) VALUES
    (201, 'sable', 'active', CURRENT_TIMESTAMP - INTERVAL '30 days'),
    (202, 'orbit', 'active', CURRENT_TIMESTAMP - INTERVAL '25 days'),
    (203, 'ember', 'flagged', CURRENT_TIMESTAMP - INTERVAL '3 days'),
    (204, 'lumen', 'active', CURRENT_TIMESTAMP - INTERVAL '12 days'),
    (205, 'drift', 'suspended', CURRENT_TIMESTAMP - INTERVAL '2 days');
