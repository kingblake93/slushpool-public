from datetime import datetime, timedelta
import requests
import pandas as pd
import json

import email, smtplib, ssl

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import json


class ApiGrabber:
    def __init__(self,
                 slush_endpoint='https://slushpool.com/stats/json/btc/',
                 btc_endpoint='https://api.coindesk.com/v1/bpi/currentprice.json'):

        slush_key = self.get_slush_key()
        self.slush_request = requests.get(slush_endpoint,
                                          headers={'SlushPool-Auth-Token': slush_key})
        self.slush_recent_blocks = json.loads(self.slush_request.content.decode())['btc']['blocks']

        self.btc_request = requests.get(btc_endpoint)
        self.btc_price = json.loads(self.btc_request.content.decode())['bpi']['USD']['rate_float']

    @staticmethod
    def get_slush_key():
        try:
            with open('.slushpool', 'r') as infile:
                infile_dict = json.load(infile)
                return infile_dict['key']
        except:
            key = input('Please input your slushpool API key: ')
            temp_dict = {'key': key}
            with open('.slushpool', 'w') as infile:
                json.dump(temp_dict, infile)
                return temp_dict['key']


def initial_build():
    api_info = ApiGrabber()

    recent_blocks = api_info.slush_recent_blocks
    btc_price = api_info.btc_price

    block_list = [int(block) for block in list(api_info.slush_recent_blocks.keys())]
    block_height = block_list[0]

    df = pd.read_csv('btc_rewards_score.csv')
    for col in df.columns:
        if col not in ('height', 'found_at', 'value', 'user_reward'):
            df = df.drop(col, axis=1)

    df.to_csv('confirmed_rewards.csv', index=False)
    df['height'] = df['height'].astype(int)

    for key, block in recent_blocks.items():
        if key not in list(df['height']):
            _ = {'height': int(key),
                 'found_at': datetime.fromtimestamp(block['date_found']).strftime('%Y-%m-%d %H:%M:%S'),
                 'value': block['value'],
                 'user_reward': block['user_reward']}

            df = df.append(_, ignore_index=True)

    df = df.sort_values(by='height')
    df.to_csv('all_rewards.csv', index=False)


def update_log():
    timestamp = datetime.now().strftime("%A, %d. %B %Y %I:%M%p")
    print(timestamp)

    df = pd.read_csv('all_rewards.csv')

    api_info = ApiGrabber()

    recent_blocks = api_info.slush_recent_blocks
    list_of_blocks = [int(blck) for blck in list(recent_blocks.keys())]
    percent_of_blocks = 100*len(list_of_blocks)/(list_of_blocks[0] - list_of_blocks[-1])

    old_length = len(df)

    block_heights = get_block_heights(df)
    next_adjustment = block_heights[-1]

    target_date, percent_capex = get_target_capex_recovery(all_rewards_df=df)

    for key, block in recent_blocks.items():
        if key not in [str(height) for height in list(df['height'])]:
            _ = {'height': int(key),
                 'found_at': datetime.fromtimestamp(block['date_found']).strftime('%Y-%m-%d %H:%M:%S'),
                 'value': block['value'],
                 'user_reward': float(block['user_reward'])}

            df = df.append(_, ignore_index=True)

            period_completion = 100 * (2016 - (next_adjustment - int(key))) / 2016
            blocks_til_adjustment = next_adjustment - int(key)

            print(f'{"*"*len("New block found!")}\n'
                  f'New block found!\n')
            print(f'Block Height: {key}')
            print(f'Block Found At: {_["found_at"]}')
            print(f'Block Value: {_["value"]}')
            print(f'Block User Reward: {_["user_reward"]} ~ ${round(api_info.btc_price*_["user_reward"], 2)}')
            print(f'Diff period: {round(period_completion, 2)}% Complete')
            print(f'Diff period: {blocks_til_adjustment} blocks remaining')
            print(f'Target Capex Recovery: {target_date}')
            print(f'{"*"*len("New block found!")}\n')

            df_today, sum_today = get_todays_reward(df)

            email_cred = get_email_cred()
            email = Email(email_cred['sender_email'], email_cred['password'],
                          recipient='blake.king@protonmail.com',
                          subject=f'New Block Found! ${round(api_info.btc_price*sum_today, 2)} Today',
                          body=f'Block Height: {key}\n'
                               f'Block Found At: {_["found_at"]}\n'
                               f'Block User Reward: {_["user_reward"]} ~ '
                               f'${round(api_info.btc_price*_["user_reward"], 2)}\n'
                               f'Diff period: {round(period_completion, 2)}% Complete\n'
                               f'Diff period: {blocks_til_adjustment} blocks remaining\n'
                               f'Target Capex Recovery: {target_date} | {percent_capex}')
            email.send()

    df = df.sort_values(by='height')
    df.to_csv('all_rewards.csv', index=False)
    new_length = len(df)

    if old_length == new_length:
        print('No new blocks found.')

    return df


def get_daily_btc(full_history_df, start=0, end=9999999, prints=True):
    _ = ApiGrabber()
    full_blocks = full_history_df

    full_blocks = full_blocks.loc[(full_blocks['height'] >= start) &
                                  (full_blocks['height'] <= end)]

    full_blocks = full_blocks.reset_index(drop=True)
    total_reward = full_blocks['user_reward'].sum()

    first_block = full_blocks['found_at'][0]
    last_block = full_blocks['found_at'][len(full_blocks)-1]
    try:
        delta = last_block - first_block
    except:
        first_block = datetime.strptime(full_blocks['found_at'][0], '%Y-%m-%d %H:%M:%S')
        last_block = datetime.strptime(full_blocks['found_at'][len(full_blocks)-1], '%Y-%m-%d %H:%M:%S')
        delta = last_block - first_block

    delta = 0.7 + delta.days + (delta.seconds / 3600)/24

    daily_average = total_reward/delta

    if prints is True:
        print(f'Current Daily Average: {round(daily_average, 6)} ~ ${round(daily_average*_.btc_price, 2)}')
        print(f'Current Monthly Average: {round(daily_average*(365/12), 6)} ~ ${round(daily_average*(365/12)*_.btc_price, 2)}')
        print(f'Total Reward: {round(total_reward, 9)} ~ ${round(total_reward*_.btc_price, 2)}')
        print(f'Time period range: {round(delta, 2)} days')
        print('-'*len(f'Current Daily Average: {round(daily_average, 6)}'))

    return daily_average, total_reward


def get_diff_period_averages(all_rewards_df):
    BLOCK_PERIOD_START = 0

    first_block = int(all_rewards_df['height'][1])
    last_block = int(all_rewards_df['height'][len(all_rewards_df)-1])

    block_heights = [BLOCK_PERIOD_START + 2016 * n for n in range(1 + round(last_block/2016))
                     if last_block > BLOCK_PERIOD_START + 2016 * n > first_block]

    pre_height = block_heights[0]-2016
    post_height = block_heights[-1]+2016
    block_heights.insert(0, pre_height)
    block_heights.append(post_height)

    for index, height in enumerate(block_heights):
        try:
            print(f'For the difficulty period from {block_heights[index]} to {block_heights[index+1]}:')
            get_daily_btc(all_rewards_df, start=block_heights[index], end=block_heights[index+1])
            period_completion = 100*(2016 - (block_heights[index+1] - last_block))/2016

            if period_completion < 100:
                print(f'Difficulty Period {round(period_completion, 2)}% complete.')
                print('\n')
            else:
                print(f'Difficulty Period completed.')
                print('\n')
        except:
            pass


def get_todays_reward(all_rewards_df):
    all_rewards_df['found_at'] = pd.to_datetime(all_rewards_df['found_at'], format="%Y-%m-%d")

    temp_df = pd.DataFrame()

    for index, rows in all_rewards_df.iterrows():
        if rows['found_at'].date() == pd.Timestamp.today().date():
            temp_df = temp_df.append(rows)

    try:
        days_sum = temp_df['user_reward'].sum()
    except:
        days_sum = 0.0

    return temp_df, days_sum


def get_block_heights(all_rewards_df):
    BLOCK_PERIOD_START = 0

    first_block = int(all_rewards_df['height'][0])
    last_block = int(all_rewards_df['height'][len(all_rewards_df)-1])

    block_heights = [BLOCK_PERIOD_START + 2016 * n for n in range(1 + round(last_block/2016))
                     if last_block > BLOCK_PERIOD_START + 2016 * n > first_block]

    pre_height = block_heights[0]-2016
    post_height = block_heights[-1]+2016
    block_heights.insert(0, pre_height)
    block_heights.append(post_height)

    return block_heights


def get_target_capex_recovery(all_rewards_df, capex=1.02397):
    daily_avg, total_reward = get_daily_btc(all_rewards_df, prints=False)

    remaining_capex = capex - total_reward

    days_capex = round(remaining_capex / daily_avg, 0)

    future_date = datetime.now() + timedelta(days=days_capex)

    return future_date.strftime("%Y-%m-%d"), round(100*(total_reward/capex), 2)


def get_cost_basis(rewards='all_rewards.csv'):
    _ = pd.read_csv(rewards)
    first_day = _.iloc[0]['found_at']
    first_day = datetime.strptime(first_day, '%Y-%m-%d %H:%M:%S')
    first_day = first_day.strftime('%Y-%m-%d')

    last_day = _.iloc[len(_) - 1]['found_at']
    last_day = datetime.strptime(last_day, '%Y-%m-%d %H:%M:%S')
    last_day = last_day.strftime('%Y-%m-%d')

    historical_data = requests.get(
        f'https://api.coindesk.com/v1/bpi/historical/close.json?start={first_day}&end={last_day}')
    bpi_dict = json.loads(historical_data.content)['bpi']

    _['found_at'] = pd.to_datetime(_['found_at'], format="%Y-%m-%d")

    for index, row in _.iterrows():
        btc_close = bpi_dict[row['found_at'].date().__str__()]
        cost_basis = btc_close * row['user_reward']
        _.loc[index, 'btc_close'] = btc_close
        _.loc[index, 'cost_basis'] = cost_basis

    writer = pd.ExcelWriter('cost_basis_report.xlsx', engine='xlsxwriter')
    _.to_excel(writer, sheet_name='Block Rewards')
    writer.save()

    return 'cost_basis_report.xlsx'


def get_email_cred():
    try:
        with open('.email_cred', 'r') as infile:
            infile_dict = json.load(infile)
            return infile_dict
    except:
        address = input('Please input your python email address: ')
        pw = input('Please input your python email pw: ')
        temp_dict = {'sender_email': address,
                     'password': pw}
        with open('.email_cred', 'w') as infile:
            json.dump(temp_dict, infile)
            return temp_dict


class Email():

    def __init__(self, sender_email, password, body, recipient, subject=''):
        '''
        Calling this class will create an EMAIL object that you can send when ready
        :param subject:
        :param body:
        :param sender_email:
        :param password:
        :param recipient:
        :return:
        '''
        self.subject = subject
        self.body = body
        self.sender_email = sender_email
        self.recipient = recipient
        self.password = password

        # Create a multipart message and set headers
        self.message = MIMEMultipart()
        self.message["From"] = self.sender_email
        self.message["To"] = self.recipient
        self.message["Subject"] = self.subject
        self.message["Bcc"] = self.recipient  # Recommended for mass emails

        # Add body to email
        self.message.attach(MIMEText(body, "plain"))

    def attach_file(self, filename):
        # Open PDF file in binary mode
        with open(filename, "rb") as attachment:
            # Add file as application/octet-stream
            # Email client can usually download this automatically as attachment
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())

        # Encode file in ASCII characters to send by email
        encoders.encode_base64(part)

        # Add header as key/value pair to attachment part
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {filename}",
        )

        # Add attachment to message and convert message to string
        self.message.attach(part)

    def send(self):
        # Log in to server using secure context and send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(self.sender_email, self.password)
            server.sendmail(self.sender_email, self.recipient, self.message.as_string())


def send_cost_basis_report(*, rewards_csv='all_rewards.csv', recipient_email='mlarking77@gmail.com'):
    filename = get_cost_basis(rewards=rewards_csv)

    email_cred = get_email_cred()
    email = Email(email_cred['sender_email'], email_cred['password'],
                  recipient=recipient_email,
                  subject=f'Cost Basis using BTC Close',
                  body=f'See attached for example cost basis report using just BTC closing price')
    email.attach_file(filename)
    email.send()


def get_todays_report(all_rewards_df):

    api = ApiGrabber()
    temp_df, days_sum = get_todays_reward(all_rewards_df=all_rewards_df)
    num_blocks = len(temp_df)
    dollar_sum = round(days_sum*api.btc_price, 2)

    return temp_df, days_sum, dollar_sum, num_blocks


if __name__ == '__main__':
    _ = pd.read_csv('all_rewards.csv')

    # send_cost_basis_report(recipient_email='blake.king@protonmail.com')

    # get_cost_basis()
    #
    data = get_todays_report(_)
    for item in data:
        print(item)
    get_diff_period_averages(_)

    get_daily_btc(full_history_df=_)
    capex_recovered, percent_complete = get_target_capex_recovery(all_rewards_df=_)
    print(f"Capex recovery by: {capex_recovered}")
    print(f"Capex recovered: {percent_complete}%")
