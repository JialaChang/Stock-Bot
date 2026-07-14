INSERT INTO stocks (ticker, name, market)
VALUES (?, ?, ?)
ON CONFLICT(ticker) DO UPDATE SET
    name=excluded.name,
    market=excluded.market
