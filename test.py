from telegram import Bot
from config import BOT_TOKEN

async def main():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id=627686670,
        text="ятебячмоки"
    )

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())