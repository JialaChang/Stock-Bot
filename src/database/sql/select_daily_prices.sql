SELECT date, open_price, high_price, low_price, close_price, adjust_close_price, volume
FROM daily_prices
WHERE ticker = ?
ORDER BY date DESC LIMIT ?
