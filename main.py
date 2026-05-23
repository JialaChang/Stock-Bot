from src.bot.dc_bot import bot, TOKEN

if __name__ == "__main__":
    try:
        bot.run(TOKEN) # pyright: ignore[reportArgumentType]
    except Exception as e:
        print(f"[System] Error : {e}")