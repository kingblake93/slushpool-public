import time
from utils import *

#  This is an infinite loop, everything within while True will
#  continue until the code crashes.

while True:
    try:
        # Get a string timestamp of RIGHT NOW in the format of
        # %A, %d. %B %Y %I:%M%p.
        timestamp = datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
        print(timestamp)

        # Run update_log(), this will do all the heavy lifting
        # of the script.
        all_blocks = update_log()

        # get_daily_btc(all_blocks)

    # This is for catching any errors. This way, the code can
    # still continue.
    except Exception as r:
        print(f'Exception {r} occurred.')

    # After exiting the Try, Except clause, wait for 20 minutes
    # and then start the infinite loop again
    time.sleep(1200)

