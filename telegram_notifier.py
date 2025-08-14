# telegram_notifier.py

import telegram
import asyncio
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

def send_telegram_message(message):
    """텔레그램 메시지를 비동기적으로 전송합니다."""
    async def main():
        try:
            bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
            await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
            print(f"텔레그램 메시지 전송 성공: {message}")
        except Exception as e:
            print(f"텔레그램 메시지 전송 실패: {e}")

    # 비동기 함수 실행
    asyncio.run(main())

if __name__ == '__main__':
    # 파일 단독 실행 시 테스트 메시지 전송
    send_telegram_message("텔레그램 알림 테스트 메시지입니다.")
