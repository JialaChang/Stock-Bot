-- ON CONFLICT upsert: update the values but keep the original id to avoid triggering FK cascade
INSERT INTO daily_prices
(ticker, date, open_price, high_price, low_price, close_price, adjust_close_price, volume)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(ticker, date) DO UPDATE SET
    open_price=excluded.open_price,
    high_price=excluded.high_price,
    low_price=excluded.low_price,
    close_price=excluded.close_price,
    adjust_close_price=excluded.adjust_close_price,
    volume=excluded.volume
