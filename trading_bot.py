import cbpro
import pandas as pd
import time
import config
import json
import os
import sys
import numpy as np


# INSTANTIATIONS PRIOR TO TRADING BELOW
CRYPTO_LIVE_PRICES = pd.DataFrame(columns=['ID', 'PRICE'])
spec_df = pd.DataFrame()
last_price = 0
print('initializing...')

# API information
API = config.CB_API
API_PRIVATE = config.CB_API_Secret
PASSPHRASE = config.CB_Passphrase
textbelt_api = config.TXTBLT_API

# Making API connection to Trading Bot portfolio
CBpro = cbpro.AuthenticatedClient(key=API,
                                  b64secret=API_PRIVATE,
                                  passphrase=PASSPHRASE)

# Making API connection to Public Client
cb_public = cbpro.PublicClient()

# FUNCTIONS BELOW


def update_data_table():
    '''To accomodate new listings'''
    data = pd.DataFrame(cb_public.get_products())
    non_USD = data[data['quote_currency'] != 'USD']
    data = data.drop(index=non_USD.index)
    stable_coin = data[data['fx_stablecoin'] == True]
    data = data.drop(index=stable_coin.index)
    post_only = data[data['post_only'] == True]
    data = data.drop(index=post_only.index)
    limit_only = data[data['limit_only'] == True]
    data = data.drop(index=limit_only.index)
    cancel_only = data[data['cancel_only'] == True]
    data = data.drop(index=cancel_only.index)
    trading_disabled = data[data['trading_disabled'] == True]
    data = data.drop(index=trading_disabled.index)
    delisted = data[data['status'] != 'online']
    data = data.drop(index=delisted.index)
    auction_mode = data[data['auction_mode'] == True]
    data = data.drop(index=auction_mode.index)
    data['base_increment'] = data['base_increment'].replace('10', -1)
    data['base_increment'] = data['base_increment'].replace('1', 0)
    data['base_increment'] = data['base_increment'].replace('0.1', 1)
    data['base_increment'] = data['base_increment'].replace('0.01', 2)
    data['base_increment'] = data['base_increment'].replace('0.001', 3)
    data['base_increment'] = data['base_increment'].replace('0.0001', 4)
    data['base_increment'] = data['base_increment'].replace('0.00001', 5)
    data['base_increment'] = data['base_increment'].replace('0.000001', 6)
    data['base_increment'] = data['base_increment'].replace('0.0000001', 7)
    data['base_increment'] = data['base_increment'].replace('0.00000001', 8)
    data['base_increment'] = data['base_increment'].replace('0.000000001', 9)
    data['base_increment'] = data['base_increment'].replace('0.0000000001', 10)
    data = data.set_index('base_currency').sort_index(ascending=True)
    irr_cols = ['base_min_size', 'base_max_size', 'quote_increment',
                'min_market_funds', 'max_market_funds', 'margin_enabled',
                'max_slippage_percentage', 'status_message', 'display_name',
                'fx_stablecoin', 'post_only', 'limit_only', 'cancel_only',
                'trading_disabled', 'status', 'auction_mode']
    data = data.drop(columns=irr_cols)
    data2 = pd.DataFrame(CBpro.get_accounts())
    data2['id_#'] = data2['id']
    cols = ['balance', 'hold', 'available',
            'profile_id', 'trading_enabled', 'id']
    data2 = data2.set_index('currency').drop(columns=cols)
    data = data.join(data2)
    return data


data = update_data_table()


def current_price(ID):
    '''Returns current price of crypto'''
    return float(cb_public.get_product_24hr_stats(ID)['last'])


def text_yg(message):
    '''Texts yg whenever crypto is bought or sold'''
    import requests
    # resp =
    requests.post('https://textbelt.com/text', {'phone': '4753551157',
                                                'message': message,
                                                'key': textbelt_api})
    # print(resp.json())


def relative_high(ID):
    '''Returns relative high of crypto'''
    candles_1d = cb_public.get_product_historic_rates(ID, granularity=86400)
    list_of_highs = []
    for day in candles_1d:
        list_of_highs.append(day[2])
    return float((pd.Series(list_of_highs)).max())


def buy(ID):
    '''Buys crypto'''
    USD_id_num = 'd752888c-f5d9-4b53-ac0f-017348119031'
    funds = round(float(CBpro.get_account(USD_id_num)['balance']), 2) - 1
    CBpro.place_market_order(product_id=ID, side='buy', funds=funds)
    buy_message = 'BOUGHT ' + ID + ' @ ' + str(current_price(ID))
    text_yg(buy_message)
    print(buy_message)


def sell(ID):
    '''Sells crypto'''
    original_coin_balance = float(CBpro.get_account(
        (data[data['id'] == ID]['id_#']).max())['balance'])
    balances = []
    round_to = (data[data['id'] == ID]['base_increment']).max()
    for DICT in CBpro.get_accounts():
        if DICT['currency'] != 'USD':
            balances.append(DICT['balance'])
    size = round(float((pd.Series(balances)).max()), round_to)
    CBpro.place_market_order(product_id=ID, side='sell', size=size)
    if float(CBpro.get_account((data[data['id'] == ID]['id_#']).max())['balance']) == original_coin_balance:
        strings = ['0', '.']
        for x in range(round_to):
            strings.append('0')
        strings.append('9')
        correction = ''.join(map(str, strings))
        correction = float(correction)
        new_size = round(original_coin_balance - correction, round_to)
        CBpro.place_market_order(product_id=ID, side='sell', size=new_size)
    sell_message = 'SOLD ' + ID + ' @ ' + str(current_price(ID))
    text_yg(sell_message)
    print(sell_message)


def update_RHs():
    LIST_IDS = [x[1][0] for x in data.iterrows()]
    RH_DF = pd.DataFrame({'ID': LIST_IDS})
    REL_HIGHS = [relative_high(ID) for ID in LIST_IDS]
    RH_DF2 = pd.DataFrame({'REL_HIGH': REL_HIGHS})
    RH_DF = RH_DF.merge(right=RH_DF2, left_index=True, right_index=True)
    return RH_DF


RH_DF = update_RHs()
current_time_check = time.localtime()


def create_bot():
    '''Creates bot'''
    while True:
        # Confirming script is running
        current_time = time.localtime()

        # Importing globals/Updating them
        global data
        global RH_DF
        global current_time_check
        # if time.localtime()[3] == current_time_check[3] + 1: <-- This updates RH_DF every hr
        if current_time_check[4] < 50:
            if time.localtime()[4] == current_time_check[4] + 10:
                current_time_check = time.localtime()
                RH_DF = update_RHs()
                data = update_data_table()
                print(
                    f'Running @: {current_time[1]}/{current_time[2]}/{current_time[0]} {current_time[3]}:{current_time[4]}:{current_time[5]}')
        elif current_time_check[4] >= 50:
            if time.localtime()[4] == (current_time_check[4] + 10) - 60:
                current_time_check = time.localtime()
                RH_DF = update_RHs()
                data = update_data_table()
                print(
                    f'Running @: {current_time[1]}/{current_time[2]}/{current_time[0]} {current_time[3]}:{current_time[4]}:{current_time[5]}')

        # Implementation of Websocket
        ID_LIST = [x[1][0] for x in data.iterrows()]

        class myWebsocketClient(cbpro.WebsocketClient):
            def on_open(self):
                self.url = 'wss://ws-feed.pro.coinbase.com/'
                self.products = ID_LIST
                self.channels = ['ticker']
                self.message_count = 0
                print('-- START --')

            def on_message(self, msg):
                self.message_count += 1
                data = json.dumps(msg)
                current_ticks = json.loads(data)
                global CRYPTO_LIVE_PRICES
                df_prices = pd.DataFrame(columns=['ID', 'PRICE'])
                for x in current_ticks:
                    crypto_price = []
                    STR_ID = ''
                    STR_PRICE = ''
                    for ID in current_ticks['product_id']:
                        STR_ID += ID
                    crypto_price.append(STR_ID)
                    for PRICE in current_ticks['price']:
                        STR_PRICE += PRICE
                    crypto_price.append(float(STR_PRICE))
                    df_prices = df_prices.append(crypto_price)
                df_prices1 = pd.DataFrame()
                df_prices1 = df_prices1.append(df_prices.iloc[0])
                df_prices1 = df_prices1.append(df_prices.iloc[1])
                c_prices = df_prices1.loc[1][0]
                c_ids = df_prices1.loc[0][0]
                df_prices1 = df_prices1.assign(PRICE=c_prices)
                df_prices1 = df_prices1.assign(ID=c_ids)
                df_prices1.pop(0)
                CRYPTO_LIVE_PRICES = CRYPTO_LIVE_PRICES.append(df_prices1)

            def on_close(self):
                print('-- END --')

        class mySubWebsocketClient(cbpro.WebsocketClient):
            def on_open(self):
                self.url = 'wss://ws-feed.pro.coinbase.com/'
                self.products = ID_LIST
                self.channels = ['ticker']
                self.message_count = 0
                print('-- START --')

            def on_message(self, msg):
                self.message_count += 1
                data = json.dumps(msg)
                current_ticks = json.loads(data)
                global spec_df
                df_prices = pd.DataFrame(columns=['ID', 'PRICE'])
                for x in current_ticks:
                    crypto_price = []
                    STR_ID = ''
                    STR_PRICE = ''
                    for ID in current_ticks['product_id']:
                        STR_ID += ID
                    crypto_price.append(STR_ID)
                    for PRICE in current_ticks['price']:
                        STR_PRICE += PRICE
                    crypto_price.append(float(STR_PRICE))
                    df_prices = df_prices.append(crypto_price)
                df_prices1 = pd.DataFrame()
                df_prices1 = df_prices1.append(df_prices.iloc[0])
                df_prices1 = df_prices1.append(df_prices.iloc[1])
                c_prices = df_prices1.loc[1][0]
                c_ids = df_prices1.loc[0][0]
                df_prices1 = df_prices1.assign(PRICE=c_prices)
                df_prices1 = df_prices1.assign(ID=c_ids)
                df_prices1.pop(0)
                spec_df = spec_df.append(df_prices1)

        class suppress_output:
            def __init__(self, suppress_stdout=False, suppress_stderr=False):
                self.suppress_stdout = suppress_stdout
                self.suppress_stderr = suppress_stderr
                self._stdout = None
                self._stderr = None

            def __enter__(self):
                devnull = open(os.devnull, "w")
                if self.suppress_stdout:
                    self._stdout = sys.stdout
                    sys.stdout = devnull

                if self.suppress_stderr:
                    self._stderr = sys.stderr
                    sys.stderr = devnull

            def __exit__(self, *args):
                if self.suppress_stdout:
                    sys.stdout = self._stdout
                if self.suppress_stderr:
                    sys.stderr = self._stderr

        WS = myWebsocketClient()
        i = 0
        with suppress_output(suppress_stdout=True, suppress_stderr=True):
            WS.start()
            while i < 10:
                time.sleep(.5)
                i += 1
            else:
                WS.close()

        global CRYPTO_LIVE_PRICES
        CRYPTO_LIVE_PRICES = CRYPTO_LIVE_PRICES.drop_duplicates()
        CRYPTO_LIVE_PRICES = CRYPTO_LIVE_PRICES.sort_values(by='ID')

        # Begin iterations to find trades
        for ID in ID_LIST:
            def find_price(ID):
                C_PRICE = CRYPTO_LIVE_PRICES.loc[CRYPTO_LIVE_PRICES['ID'] == ID]['PRICE'].max(
                )
                return C_PRICE

            def find_RH(ID):
                RH = RH_DF.loc[RH_DF['ID'] == ID]['REL_HIGH'].max()
                return RH
            if find_price(ID) >= find_RH(ID):
                if data[data['id'] == ID]['id_#'].max() is not np.NAN:
                    orig_USD_balance = float(CBpro.get_account(
                        'd752888c-f5d9-4b53-ac0f-017348119031')['balance'])
                    buy(ID)
                    price_bought_at = find_price(ID)
                    new_USD_balance = float(CBpro.get_account(
                        'd752888c-f5d9-4b53-ac0f-017348119031')['balance'])
                    if orig_USD_balance > new_USD_balance:
                        def pct_chnge(initial_price, new_price):
                            return (((new_price - initial_price) / abs(initial_price)) * 100)

                        def do_WS_find_ID_price(ID):
                            sub_WS = mySubWebsocketClient()
                            global spec_df
                            global last_price
                            spec_df = pd.DataFrame()
                            iter = 0
                            with suppress_output(suppress_stdout=True, suppress_stderr=True):
                                sub_WS.start()
                                while iter < 100:
                                    time.sleep(.01)
                                    iter += 1
                                else:
                                    sub_WS.close()
                            try:
                                new_prices = str(
                                    (spec_df.loc[spec_df['ID'] == ID]['PRICE'])[0])
                                last_price = str(
                                    (spec_df.loc[spec_df['ID'] == ID]['PRICE'][0]))
                                return float(new_prices)
                            except:
                                return float(last_price)
                        i = 1
                        while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > -10.0:
                            if i > 1:
                                break
                            elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 10.0:
                                i = 2
                                while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 0.0:
                                    if i > 2:
                                        break
                                    elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 20.0:
                                        i = 3
                                        while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 10.0:
                                            if i > 3:
                                                break
                                            elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 30.0:
                                                i = 4
                                                while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 20.0:
                                                    if i > 4:
                                                        break
                                                    elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 40.0:
                                                        i = 5
                                                        while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 30.0:
                                                            if i > 5:
                                                                break
                                                            elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 50.0:
                                                                i = 6
                                                                while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 40.0:
                                                                    if i > 6:
                                                                        break
                                                                    elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 60.0:
                                                                        i = 7
                                                                        while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 50.0:
                                                                            if i > 7:
                                                                                break
                                                                            elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 70.0:
                                                                                i = 8
                                                                                while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 60.0:
                                                                                    if i > 8:
                                                                                        break
                                                                                    elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 80.0:
                                                                                        i = 9
                                                                                        while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 70.0:
                                                                                            if i > 9:
                                                                                                break
                                                                                            elif pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 90.0:
                                                                                                i = 10
                                                                                                while pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) > 80.0:
                                                                                                    if pct_chnge(price_bought_at, do_WS_find_ID_price(ID)) >= 100:
                                                                                                        sell(
                                                                                                            ID)
                                                                                                        break
                                                                                                else:
                                                                                                    sell(
                                                                                                        ID)

                                                                                        else:
                                                                                            sell(
                                                                                                ID)

                                                                                else:
                                                                                    sell(
                                                                                        ID)

                                                                        else:
                                                                            sell(
                                                                                ID)

                                                                else:
                                                                    sell(ID)

                                                        else:
                                                            sell(ID)

                                                else:
                                                    sell(ID)

                                        else:
                                            sell(ID)

                                else:
                                    sell(ID)

                        else:
                            sell(ID)
                    else:
                        ERROR = 'SOMETHING WENT WRONG!'
                        text_yg(ERROR)
        CRYPTO_LIVE_PRICES = pd.DataFrame(columns=['ID', 'PRICE'])


print('starting...')
print(
    f'Running @: {current_time_check[1]}/{current_time_check[2]}/{current_time_check[0]} {current_time_check[3]}:{current_time_check[4]}:{current_time_check[5]}')
create_bot()
