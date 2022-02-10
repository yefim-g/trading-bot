# from flask import Flask
import cbpro
import pandas as pd
import time
import config

# ONE DAY ADD THIS TO BOT:
# BEFORE SELLING TAKE 20% OF GAIN OVER $5000,
# TRANSFER TO EXODUS WALLET
# ALSO
# TAKE 5% OF ACTUALIZED *GAIN*,
# DEPOSIT TO USD ACCOUNT ON COINBASE

# CONSIDER ADDING ASSERTIONS


def create_bot():
    '''Creates bot'''
    while True:
        time.sleep(30)
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

        # Getting data about all tradable crypto
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
        data['base_increment'] = data['base_increment'].replace(
            '0.00000001', 8)
        data['base_increment'] = data['base_increment'].replace(
            '0.000000001', 9)
        data['base_increment'] = data['base_increment'].replace(
            '0.0000000001', 10)
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
            candles_1d = cb_public.get_product_historic_rates(
                ID, granularity=86400)
            list_of_highs = []
            for day in candles_1d:
                list_of_highs.append(day[2])
            return float((pd.Series(list_of_highs)).max())

        def buy(ID):
            '''Buys crypto'''
            USD_id_num = 'd752888c-f5d9-4b53-ac0f-017348119031'
            funds = round(float(CBpro.get_account(
                USD_id_num)['balance']), 2) - 1
            CBpro.place_market_order(product_id=ID, side='buy', funds=funds)
            buy_message = 'BOUGHT ' + ID + ' @ ' + str(current_price(ID))
            text_yg(buy_message)

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
                CBpro.place_market_order(
                    product_id=ID, side='sell', size=new_size)
            sell_message = 'SOLD ' + ID + ' @ ' + str(current_price(ID))
            text_yg(sell_message)

        ids = [row[1][0] for row in data.iterrows()]
        for ID in ids:
            if current_price(ID) >= relative_high(ID):
                orig_USD_balance = float(CBpro.get_account(
                    'd752888c-f5d9-4b53-ac0f-017348119031')['balance'])
                buy(ID)
                orig_coin_balance = float(CBpro.get_account(
                    data[data['id'] == ID]['id_#'].max())['balance'])
                price_bought_at = current_price(id)
                new_USD_balance = float(CBpro.get_account(
                    'd752888c-f5d9-4b53-ac0f-017348119031')['balance'])
                if orig_USD_balance >= new_USD_balance:
                    def pct_chnge(initial_price, new_price):
                        return (((new_price - initial_price) / abs(initial_price)) * 100)
                    while pct_chnge(price_bought_at, current_price(ID)) > -10.0:
                        time.sleep(25)
                        new_coin_balance = float(CBpro.get_account(
                            data[data['id'] == ID]['id_#'].max())['balance'])
                        if new_coin_balance != orig_coin_balance:
                            break
                        elif pct_chnge(price_bought_at, current_price(ID)) >= 10.0:
                            while pct_chnge(price_bought_at, current_price(ID)) > 0.0:
                                time.sleep(25)
                                new_coin_balance = float(CBpro.get_account(
                                    data[data['id'] == ID]['id_#'].max())['balance'])
                                if new_coin_balance != orig_coin_balance:
                                    break
                                elif pct_chnge(price_bought_at, current_price(ID)) >= 20.0:
                                    while pct_chnge(price_bought_at, current_price(ID)) > 10.0:
                                        time.sleep(25)
                                        new_coin_balance = float(CBpro.get_account(
                                            data[data['id'] == ID]['id_#'].max())['balance'])
                                        if new_coin_balance != orig_coin_balance:
                                            break
                                        elif pct_chnge(price_bought_at, current_price(ID)) >= 30.0:
                                            while pct_chnge(price_bought_at, current_price(ID)) > 20.0:
                                                time.sleep(25)
                                                new_coin_balance = float(CBpro.get_account(
                                                    data[data['id'] == ID]['id_#'].max())['balance'])
                                                if new_coin_balance != orig_coin_balance:
                                                    break
                                                elif pct_chnge(price_bought_at, current_price(ID)) >= 40.0:
                                                    while pct_chnge(price_bought_at, current_price(ID)) > 30.0:
                                                        time.sleep(25)
                                                        new_coin_balance = float(CBpro.get_account(
                                                            data[data['id'] == ID]['id_#'].max())['balance'])
                                                        if new_coin_balance != orig_coin_balance:
                                                            break
                                                        elif pct_chnge(price_bought_at, current_price(ID)) >= 50.0:
                                                            while pct_chnge(price_bought_at, current_price(ID)) > 40.0:
                                                                time.sleep(25)
                                                                new_coin_balance = float(CBpro.get_account(
                                                                    data[data['id'] == ID]['id_#'].max())['balance'])
                                                                if new_coin_balance != orig_coin_balance:
                                                                    break
                                                                elif pct_chnge(price_bought_at, current_price(ID)) >= 60.0:
                                                                    while pct_chnge(price_bought_at, current_price(ID)) > 50.0:
                                                                        time.sleep(
                                                                            25)
                                                                        new_coin_balance = float(CBpro.get_account(
                                                                            data[data['id'] == ID]['id_#'].max())['balance'])
                                                                        if new_coin_balance != orig_coin_balance:
                                                                            break
                                                                        elif pct_chnge(price_bought_at, current_price(ID)) >= 70.0:
                                                                            while pct_chnge(price_bought_at, current_price(ID)) > 60.0:
                                                                                time.sleep(
                                                                                    25)
                                                                                new_coin_balance = float(CBpro.get_account(
                                                                                    data[data['id'] == ID]['id_#'].max())['balance'])
                                                                                if new_coin_balance != orig_coin_balance:
                                                                                    break
                                                                                elif pct_chnge(price_bought_at, current_price(ID)) >= 80.0:
                                                                                    while pct_chnge(price_bought_at, current_price(ID)) > 70.0:
                                                                                        time.sleep(
                                                                                            25)
                                                                                        new_coin_balance = float(CBpro.get_account(
                                                                                            data[data['id'] == ID]['id_#'].max())['balance'])
                                                                                        if new_coin_balance != orig_coin_balance:
                                                                                            break
                                                                                        elif pct_chnge(price_bought_at, current_price(ID)) >= 90.0:
                                                                                            while pct_chnge(price_bought_at, current_price(ID)) > 80.0:
                                                                                                time.sleep(
                                                                                                    25)
                                                                                                if pct_chnge(price_bought_at, current_price(ID)) >= 100:
                                                                                                    sell(
                                                                                                        ID)
                                                                                                    break
                                                                                            else:
                                                                                                sell(
                                                                                                    ID)
                                                                                                break
                                                                                    else:
                                                                                        sell(
                                                                                            ID)
                                                                                        break
                                                                            else:
                                                                                sell(
                                                                                    ID)
                                                                                break
                                                                    else:
                                                                        sell(
                                                                            ID)
                                                                        break
                                                            else:
                                                                sell(ID)
                                                                break
                                                    else:
                                                        sell(ID)
                                                        break
                                            else:
                                                sell(ID)
                                                break
                                    else:
                                        sell(ID)
                                        break
                            else:
                                sell(ID)
                                break
                    else:
                        sell(ID)
                        break


print('starting...')
create_bot()

# FIGURE OUT API STUFF, COMMIT TO GITHUB (PRIVATE)
# DEPLOY TO HEROKU
