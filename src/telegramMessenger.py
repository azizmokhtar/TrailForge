import asyncio
from telegram import Bot

TOKEN = ""
chat_id = ''
# Channel ID Sample: -1001829542722
class Messenger:
    def __init__(self):
        self.bot = Bot(token=TOKEN)
        self.chat_id = chat_id
        
    async def send_message(self, text):
        try:
            async with self.bot:
                await self.bot.send_message(text=text, chat_id=self.chat_id)
        except Exception as e:
            print(f"Error sending telegram message: {e}")

async def main():
    # Create messenger instance
    messenger_instance = Messenger()
    # Sending a message
    await messenger_instance.send_message(text='TeSt')

if __name__ == '__main__':
    asyncio.run(main())