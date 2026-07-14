SELECT
    date,
    open_price AS Open,
    high_price AS High,
    low_price AS Low,
    close_price AS Close,
    adjust_close_price AS AdjClose,
    volume AS Volume
FROM daily_prices
WHERE ticker = ? AND date >= ?
ORDER BY date ASC
