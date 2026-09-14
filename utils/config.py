import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
LOG_CHANNEL_ID = os.getenv('LOG_CHANNEL_ID')
SUPPORT_WEBHOOK_URL = os.getenv('SUPPORT_WEBHOOK_URL') or os.getenv('LOG_WEBHOOK_URL')
DATABASE_ENABLED = os.getenv('DATABASE_ENABLED', 'false').lower() == 'true'

OWNER_ID = 1013851779886231685
