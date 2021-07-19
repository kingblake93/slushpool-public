import random
import time
from utils import *

while True:
    try:
        timestamp = datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
        print(timestamp)

        all_blocks = update_log()

        # get_daily_btc(all_blocks)

    except Exception as r:
        print(f'Exception {r} occurred.')
    time.sleep(1200)

