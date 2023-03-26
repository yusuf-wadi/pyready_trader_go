
import math
import numpy as np
import heapq
from hyperopt import fmin, tpe, hp
import pandas as pd
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

current_pos = [0,0]
tick = 0
df = pd.read_csv('score_data/market2.csv')
abs_time = df["Time"]
teams = len(df['Team'].unique())
ratios = df['EtfPrice'][::teams]/df['FuturePrice'][::teams]
ratios = ratios.reset_index(drop=True)
# etf_balances =
cur_ratio = 0
buy_signals = []
sell_signals = []
profits = []
current_profit = 0
prev_sig = -1
# parameters
rsi = []
movingAvg = 0
movingSD = 0
stoch_rsi = 0
rollingRatios = []
high_bollinger_band = 1
low_bollinger_band = 1
price_vol_side = {}
active_orders = {}
trade_history = []
total_profit = 0


def calculate_rolling_average_50(window):
    global rollingRatios
    global tick
    sum = 0
    for i in range(tick - window, tick-1):
        sum += rollingRatios[i]
    return sum / window


def calculate_rolling_sd_50(window):
    global rollingRatios
    global tick
    global movingAvg
    sum = 0
    for i in range(tick - window, tick-1):
        sum += (rollingRatios[i] - movingAvg) ** 2
    return math.sqrt(sum / (window - 1))


def calc_rsi(window):
    global rollingRatios
    #global rsi_window
    global rsi
# Calculate the rsi
    if len(rollingRatios) > window:
        diff = np.diff(rollingRatios[-window:])
        up = np.sum(diff[diff >= 0])
        down = np.sum(-diff[diff < 0])
        rs = up/down if down != 0 else 0
        nRSI = 100 - (100 / (1 + rs))
        rsi.append(nRSI)


def calc_stochastic_rsi(window):
    global rollingRatios
    global rsi
    global stoch_rsi
    # Calculate the stochastic RSI
    calc_rsi(window)
    stoch_window = window

    if len(rollingRatios) > window:
        rsi_range = np.max(rsi[-stoch_window:]) - np.min(rsi[-stoch_window:])
        if rsi_range != 0:
            stoch_rsi = (rsi[-1] - np.min(rsi[-stoch_window:])) / rsi_range
        else:
            stoch_rsi = 0
        stoch_rsi = stoch_rsi
    else:
        stoch_rsi = 0


def bollinger_bands(bWidth, mAVG, mSD, bOffset):
    """
    ### a common technical indicator:

    Bollinger Bands consist of three lines: a moving average (usually a simple moving average) that represents the average price of the instrument,
    an upper band that is a certain number of standard deviations above the moving average, and a lower band that is a certain number of standard deviations below the moving average.
    The standard deviation is a measure of how much the price varies from the average.

    Bollinger Bands can be used to generate trading signals based on various rules, such as when the price touches or crosses one of the bands, when the bands widen or narrow, when the price moves above or below the moving average, etc. Different traders may use different settings for Bollinger Bands depending on their preferences and strategies34
    """
    global rollingRatios
    global high_bollinger_band
    global low_bollinger_band

    # rollingPrices.pop(0)
    # rollingPrices.append(ratio)

    # Calculate the moving average.
    MA = mAVG
    # Calculate the moving standard deviation.
    SD = mSD

    # Set the bollinger band.
    high_bollinger_band = MA + bWidth * SD
    low_bollinger_band = MA - bWidth * SD + bOffset
    #print(high_bollinger_band, low_bollinger_band)


def normal_cdf(x, mu, sigma):
    if sigma == 0:
        if x < mu:
            return 0.0
        elif x > mu:
            return 1.0
        else:
            return 0.5
    else:
        z = (x - mu) / (sigma * math.sqrt(2))
        return 0.5 * (1 + math.erf(z))

# helper function


def calc_profit(prev):
    global sell_signals
    global buy_signals
    global profits
    global cur_ratio

    current_profit = 0
    #print(f'prev: {prev_sig}')
    if prev == 0:
        # print(cur_ratio)
        current_profit = (sell_signals[-1]/cur_ratio) - 1
    if prev == 1:
        current_profit = (cur_ratio/buy_signals[-1]) - 1

    profits.append(current_profit)
    # print(current_profit)
    # print(profits)


def calc_profit_HFT(bid_price, ask_price, executed_price_ASK, executed_price_BID):
    global profits
    # executed at the best bid or ask price, no profit or loss
    profit = 0
    
    if executed_price_ASK != 0:
        # executed a sell trade at a higher price than the best ask
        profit += (ask_price/executed_price_ASK) - 1
    if executed_price_BID != 0:
        # executed a buy trade at a lower price than the best bid
        profit += (executed_price_BID/bid_price) - 1

    profits.append(profit)

# abstracted function


def trade(this_ratio, parm):

    global rollingRatios
    global movingAvg
    global movingSD
    global tick
    global stoch_rsi
    global prev_sig
    global buy_signals
    global sell_signals
    global cur_ratio
    global high_bollinger_band
    global low_bollinger_band
    global profits
    global abs_time

    time = round(abs_time[tick])
    data_at_time = price_vol_side[time]

    # cur_ratio = this_ratio
    # # print(cur_ratio)
    # rollingRatios.append(cur_ratio)

    instrument = 1
    best_asks1 = {"price": heapq.nsmallest(5, data_at_time[f'A{instrument}']["Price"]), "vol": heapq.nlargest(
        5, data_at_time[f'A{instrument}']["Volume"])}
    best_bids1 = {"price": heapq.nlargest(5, data_at_time[f'B{instrument}']["Price"]), "vol": heapq.nlargest(
        5, data_at_time[f'B{instrument}']["Volume"])}
    # conditions

    # if tick >= parm['Window']:
    #     movingAvg = calculate_rolling_average_50(int(parm['Window']))
    #     movingSD = calculate_rolling_sd_50(int(parm['Window']))

    #     if parm["name"] == "ZSRSI":

    #         Z = (cur_ratio - movingAvg)/movingSD
    #         conditions = {
    #                 "ZSRSI_SELL" : Z > parm['Z_high'] and stoch_rsi > parm['stoch_rs_high'],
    #                 "ZSRSI_BUY" : Z < parm['Z_low'] and stoch_rsi < parm['stoch_rs_low'],
    #               }

    #         calc_stochastic_rsi(int(parm['SRSIWindow']))

    #         if conditions["ZSRSI_SELL"]:# sell in pos
    #             sell_signals.append(cur_ratio)
    #             calc_profit(prev_sig)
    #             # if prev_sig == 1:
    #             #     calc_profit(prev_sig)
    #             # elif prev_sig == None:
    #             #     calc_profit(prev_sig)
    #             prev_sig = 0
    #         elif conditions["ZSRSI_BUY"]:# buy in pos
    #             buy_signals.append(cur_ratio)
    #             calc_profit(prev_sig)
    #             # if prev_sig == 0:
    #             #     calc_profit(prev_sig)
    #             # elif prev_sig == None:
    #             #     calc_profit(prev_sig)
    #             prev_sig = 1
    #         else:
    #             movingAvSmall = calculate_rolling_average_50(int(parm['smallWindow']))
    #             movingSDSmall = calculate_rolling_average_50(int(parm['smallWindow']))
    #             Z = (cur_ratio - movingAvSmall)/movingSDSmall
    #             calc_stochastic_rsi(int(parm["SRSIWindowSmall"]))

    #             if conditions["ZSRSI_SELL"]:# sell in pos
    #                 sell_signals.append(cur_ratio)
    #                 calc_profit(prev_sig)
    #                 # if prev_sig == 1:
    #                 #     calc_profit(prev_sig)
    #                 # elif prev_sig == None:
    #                 #     calc_profit(prev_sig)
    #                 prev_sig = 0
    #             elif conditions["ZSRSI_BUY"]:# buy in pos
    #                 buy_signals.append(cur_ratio)
    #                 calc_profit(prev_sig)
    #                 # if prev_sig == 0:
    #                 #     calc_profit(prev_sig)
    #                 # elif prev_sig == None:
    #                 #     calc_profit(prev_sig)
    #                 prev_sig = 1

    #     elif parm["name"] == "Bollis":
    #         #print("BALLER")
    #         #print("check")
    #         movingAvg = calculate_rolling_average_50(int(parm["BWindow"]))
    #         movingSD = calculate_rolling_sd_50(int(parm["BWindow"]))
    #         bollinger_bands(parm["band_width"], movingAvg, movingSD, parm["band_offset"])
    #         #print(f'high: {high_bollinger_band} low: {low_bollinger_band} cur: {cur_ratio}')
    #         conditions = {
    #                 "Bolli_SELL" : cur_ratio > high_bollinger_band,
    #                 "Bolli_BUY" : cur_ratio < low_bollinger_band,
    #               }
    #         if conditions["Bolli_SELL"]:# sell in pos
    #             #print("sell bolli")
    #             #print(parm["band_width"])
    #             sell_signals.append(cur_ratio)
    #             #calc_profit(prev_sig)
    #             # if prev_sig == 1:
    #             #     calc_profit(prev_sig)
    #             # elif prev_sig == None:
    #             #     calc_profit(prev_sig)
    #             prev_sig = 0
    #         elif conditions["Bolli_BUY"]:# buy in pos
    #             #print("buy bolli")
    #             buy_signals.append(cur_ratio)
    #             calc_profit(prev_sig)
    #             # if prev_sig == 0:
    #             #     calc_profit(prev_sig)
    #             # elif prev_sig == None:
    #             #     calc_profit(prev_sig)
    #             prev_sig = 1
    #         #print(profits, "hi")

# Initialize the trade history
    global current_pos
    if parm["name"] == "HTF":
        if tick > 5:
            lots = int(parm["lot_size"])
            mid_price = (best_asks1["price"][0] + best_bids1["price"][0]) / 2
            # Use a wider spread for more liquidity
            spread = (best_asks1["price"][0] - best_bids1["price"][0]) * int(parm["spread_scale"])
            new_bid_price = int(mid_price - spread / 2)
            new_ask_price = int(mid_price + spread / 2)
            # Calculate the total volume at or below the best bid price and the total volume at or above the best ask price
            ask_mean = np.mean(best_asks1["price"])
            ask_std = np.sqrt(np.sum((best_asks1["price"][0] - ask_mean)**2) / (len(best_asks1["price"]) - 1))

            bid_mean = np.mean(best_bids1["price"])
            bid_std = np.sqrt(np.sum((best_bids1["price"][0] - bid_mean)**2) / (len(best_bids1["price"]) - 1))
            bid_liquidity = sum(best_bids1['vol']) + lots
            ask_liquidity = sum(best_asks1['vol']) + lots

            buy_prob = normal_cdf(new_bid_price, mid_price, bid_std) * (bid_liquidity / (bid_liquidity + ask_liquidity)) * 1/lots
            sell_prob = (1 - normal_cdf(new_ask_price, mid_price, ask_std)) * (ask_liquidity / (bid_liquidity + ask_liquidity))* 1/lots
            # Set the weights for each probability
            # vol_weight = 0.6  # parm["w1"]
            # price_weight = 0.4  # parm["w2"]

            # Set a minimum probability threshold to avoid placing orders with low chances of being filled
            min_prob_threshold = 0.2*1/lots
            cur_bid = 0
            cur_ask = 0
            # Check if the probabilities are above the minimum threshold and place orders accordingly
            if buy_prob > min_prob_threshold:
                cur_bid = new_bid_price * lots
                #current_pos[1] = lots
            if sell_prob > min_prob_threshold:
                cur_ask = new_ask_price * lots
                #current_pos[0] = lots
            
            # Calculate profit based on the trade history
            calc_profit_HFT(bid_price=best_bids1["price"][0], ask_price=best_asks1["price"]
                            [0], executed_price_ASK=cur_ask, executed_price_BID=cur_bid)


def optimize_parameters():
    window = hp.quniform('def_Window', 50, 120, q=1)
    windowSmall = hp.quniform('smallDef_Window', 20, 50, q=1)

    param_space = hp.choice("indicators",
                            [{
                                "name": "ZSRS",
                                "Z_high": hp.quniform("Zh", 1.00, 1.2, q=0.001),
                                "Z_low": hp.quniform("Zl", 0.7, 1.00, q=0.001),
                                "stoch_rs_high": hp.quniform("str_hi", 0.55, 0.9, q=0.001),
                                "stoch_rs_low": hp.quniform("str_lo", 0.1, 0.45, q=0.001),
                                "Window": window,
                                "SRSIWindow": hp.quniform("srsi_Window", 10, 40, q=1),
                                "SRSIWindowSmall": hp.quniform("srsi_Windowsmall", 2, 10, q=1),
                                "smallWindow": windowSmall
                            },
                                {
                                "name": "Boll",
                                "Window": window,
                                "BWindow": hp.quniform("b_Window", 10, 50, q=1),
                                "band_width": hp.quniform("b_width", 1, 2.5, q=0.1),
                                "band_offset": hp.quniform("b_offset", 0.5, 0.9, q=0.1),
                                "smallWindow": windowSmall
                            },
                                {
                                "name": "HTF",
                                "lot_size": hp.quniform("lots", 10, 100, q=1),
                                "spread_scale" : hp.quniform("spread_scalar", 0, 5, q=1)
                            }
                            ])

    best = fmin(fn=run,
                space=param_space,
                algo=tpe.suggest,
                max_evals=100)

    print("Best parameters found: ", best)
    return best


def reset_globals():
    globals_dict = globals()
    for key, value in globals_dict.items():
        #del globals()[key]
        if key == 'WINDOW_SIZE':
            continue
        elif key == 'high_bollinger_band':
            globals()[key] = 1
        elif key == 'low_bollinger_band':
            globals()[key] = 1
        elif key == 'prev_sig':
            globals()[key] = -1
        elif type(value) == int:
            globals()[key] = int(0)
        elif type(value) == list:
            globals()[key] = list([])
        elif key == "current_pos":
            globals()[key] = [0,0]


def run(parm):
    global ratios
    global tick
    global profits

    for i in range(899):
        trade(i, parm)
        tick += 1
        # print(tick)

    temp_profits = profits

    # reset globals
    reset_globals()
    ###
    cum_profits = -(sum(temp_profits))
    # if parm["name"] == "Bollis":
    #     print(parm["name"], cum_profits)
    return cum_profits


if __name__ == '__main__':

    datas = ["data/market_data1.csv", "data/market_data2.csv",
             "data/market_data3.csv", "data/market_data4.csv", "data/market_data6.csv"]

    # read in csv data
    dataF = pd.read_csv(datas[0])

    # create a new column to round time
    dataF['rounded_time'] = dataF.Time.round()

    # filter dataframe to only keep relevant orders
    dataF_relevant = dataF.loc[dataF['Operation'] == 'Insert', [
        'rounded_time', 'Instrument', 'Side', 'Volume', 'Price']]

    # create a dictionary to store dataframes
    tick_dict = {}
    
    # iterate through rounded_time values
    for t in dataF['rounded_time'].unique():
        # create temporary dataframe to store data
        dataF_temp = pd.DataFrame()
        # filter dataframe to only keep orders at given time t
        dataF_temp = dataF_relevant.loc[dataF['rounded_time'] == t]

        dataF_0 = dataF_temp.loc[dataF_temp['Instrument'] == 0]
        dataF_1 = dataF_temp.loc[dataF_temp['Instrument'] == 1]
        # split dataframe into 'A' and 'B' orders
        dataF_A0 = dataF_0.loc[dataF_temp['Side'] == 'A']
        dataF_B0 = dataF_0.loc[dataF_temp['Side'] == 'B']
        dataF_A1 = dataF_1.loc[dataF_temp['Side'] == 'A']
        dataF_B1 = dataF_1.loc[dataF_temp['Side'] == 'B']

        # store dataframes in dictionary
        tick_dict[t] = {"A0": dataF_A0, "B0": dataF_B0,
                        "A1": dataF_A1, "B1": dataF_B1}

    # print dictionary
    price_vol_side = tick_dict
    
    
    # print(tick_dict)
    optimize_parameters()
