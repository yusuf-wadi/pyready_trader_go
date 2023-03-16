
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import pandas as pd
from hyperopt import fmin, tpe, hp
import numpy as np
import math
tick = 0
df = pd.read_csv('score_data/market2.csv')
teams = len(df['Team'].unique())
ratios = df['EtfPrice'][::teams]/df['FuturePrice'][::teams]
ratios = ratios.reset_index(drop=True)
#etf_balances = 
cur_ratio = 0
buy_signals = []
sell_signals = []
profits = []
current_profit = 0
prev_sig = -1
#parameters
rsi = []
movingAvg = 0
movingSD = 0
stoch_rsi = 0
rollingPrices = []
high_bollinger_band = 1
low_bollinger_band = 1
price_vol_side = {}
lot_size = 10

def calculate_rolling_average_50(window):
    global rollingPrices
    global tick
    sum = 0
    for i in range(tick -window, tick-1):
        sum += rollingPrices[i]
    return sum / window

def calculate_rolling_sd_50(window):
    global rollingPrices
    global tick
    global movingAvg
    sum = 0
    for i in range(tick -window, tick-1):
        sum += (rollingPrices[i] - movingAvg) ** 2
    return math.sqrt(sum / (window - 1))


def calc_rsi(window):
    global rollingPrices
    #global rsi_window
    global rsi
# Calculate the rsi
    if len(rollingPrices) > window:
        diff = np.diff(rollingPrices[-window:])
        up = np.sum(diff[diff>=0])
        down = np.sum(-diff[diff<0])
        rs = up/down if down != 0 else 0
        nRSI = 100 - (100 / (1 + rs))
        rsi.append(nRSI)
                    
def calc_stochastic_rsi(window):
    global rollingPrices
    global rsi
    global stoch_rsi
    # Calculate the stochastic RSI
    calc_rsi(window)
    stoch_window = window 
    
    if len(rollingPrices) > window:
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
    global rollingPrices
    global high_bollinger_band
    global low_bollinger_band

    
    #rollingPrices.pop(0)
    #rollingPrices.append(ratio)

    # Calculate the moving average.
    MA = mAVG
    # Calculate the moving standard deviation.
    SD = mSD

    # Set the bollinger band.
    high_bollinger_band = MA + bWidth * SD 
    low_bollinger_band = MA - bWidth * SD + bOffset
    #print(high_bollinger_band, low_bollinger_band)

# helper function  
def calc_profit(prev):
    global sell_signals
    global buy_signals
    global profits
    global cur_ratio
    
    current_profit = 0
    #print(f'prev: {prev_sig}')
    if prev == 0:
        #print(cur_ratio)
        current_profit = (sell_signals[-1]/cur_ratio) - 1
    if prev == 1:
        current_profit = (cur_ratio/buy_signals[-1]) - 1
        
    profits.append(current_profit)
    #print(current_profit)
    #print(profits)

def start():
    return # placeholder

#abstracted function
def trade(this_ratio, parm):
    
    global rollingPrices
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
    
    cur_ratio = this_ratio
    #print(cur_ratio)
    rollingPrices.append(cur_ratio)

    
    #conditions

    if tick >= parm['Window']:
        movingAvg = calculate_rolling_average_50(int(parm['Window']))
        movingSD = calculate_rolling_sd_50(int(parm['Window']))
        
        
        if parm["name"] == "ZSRSI":
            
            Z = (cur_ratio - movingAvg)/movingSD
            conditions = {
                    "ZSRSI_SELL" : Z > parm['Z_high'] and stoch_rsi > parm['stoch_rs_high'],
                    "ZSRSI_BUY" : Z < parm['Z_low'] and stoch_rsi < parm['stoch_rs_low'],
                  }
           
            calc_stochastic_rsi(int(parm['SRSIWindow']))
            
            if conditions["ZSRSI_SELL"]:# sell in pos
                sell_signals.append(cur_ratio)
                calc_profit(prev_sig)
                # if prev_sig == 1:
                #     calc_profit(prev_sig)
                # elif prev_sig == None:
                #     calc_profit(prev_sig)
                prev_sig = 0
            elif conditions["ZSRSI_BUY"]:# buy in pos
                buy_signals.append(cur_ratio)
                calc_profit(prev_sig)
                # if prev_sig == 0:
                #     calc_profit(prev_sig)
                # elif prev_sig == None:
                #     calc_profit(prev_sig)
                prev_sig = 1
            else:
                movingAvSmall = calculate_rolling_average_50(int(parm['smallWindow']))
                movingSDSmall = calculate_rolling_average_50(int(parm['smallWindow']))
                Z = (cur_ratio - movingAvSmall)/movingSDSmall
                calc_stochastic_rsi(int(parm["SRSIWindowSmall"]))
                
                if conditions["ZSRSI_SELL"]:# sell in pos
                    sell_signals.append(cur_ratio)
                    calc_profit(prev_sig)
                    # if prev_sig == 1:
                    #     calc_profit(prev_sig)
                    # elif prev_sig == None:
                    #     calc_profit(prev_sig)
                    prev_sig = 0
                elif conditions["ZSRSI_BUY"]:# buy in pos
                    buy_signals.append(cur_ratio)
                    calc_profit(prev_sig)
                    # if prev_sig == 0:
                    #     calc_profit(prev_sig)
                    # elif prev_sig == None:
                    #     calc_profit(prev_sig)
                    prev_sig = 1
                
        elif parm["name"] == "Bollis":
            #print("BALLER")
            #print("check")
            movingAvg = calculate_rolling_average_50(int(parm["BWindow"]))
            movingSD = calculate_rolling_sd_50(int(parm["BWindow"]))
            bollinger_bands(parm["band_width"], movingAvg, movingSD, parm["band_offset"])
            #print(f'high: {high_bollinger_band} low: {low_bollinger_band} cur: {cur_ratio}')
            conditions = {
                    "Bolli_SELL" : cur_ratio > high_bollinger_band,
                    "Bolli_BUY" : cur_ratio < low_bollinger_band,
                  }
            if conditions["Bolli_SELL"]:# sell in pos
                #print("sell bolli")
                #print(parm["band_width"])
                sell_signals.append(cur_ratio)
                #calc_profit(prev_sig)
                # if prev_sig == 1:
                #     calc_profit(prev_sig)
                # elif prev_sig == None:
                #     calc_profit(prev_sig)
                prev_sig = 0
            elif conditions["Bolli_BUY"]:# buy in pos
                #print("buy bolli")
                buy_signals.append(cur_ratio)
                calc_profit(prev_sig)
                # if prev_sig == 0:
                #     calc_profit(prev_sig)
                # elif prev_sig == None:
                #     calc_profit(prev_sig)
                prev_sig = 1
            #print(profits, "hi")
            


def optimize_parameters():
    window = hp.quniform('def_Window', 50, 120, q = 1)
    windowSmall = hp.quniform('smallDef_Window', 20,50, q=1)
    
    param_space = hp.choice("indicators",
    [{
    "name" : "ZSRSI",
    "Z_high": hp.quniform("Zh", 1.00, 1.2,q=0.001),
    "Z_low": hp.quniform("Zl", 0.7,1.00,q=0.001),
    "stoch_rs_high": hp.quniform("str_hi", 0.55, 0.9,q=0.001),
    "stoch_rs_low": hp.quniform("str_lo", 0.1, 0.45,q=0.001),
    "Window": window,
    "SRSIWindow": hp.quniform("srsi_Window", 10,40, q = 1),
    "SRSIWindowSmall" : hp.quniform("srsi_Windowsmall", 2, 10, q =1),
    "smallWindow" : windowSmall
    },
     {
    "name" : "Bollis",
    "Window": window,
    "BWindow": hp.quniform("b_Window", 10,50, q = 1),
    "band_width": hp.quniform("b_width", 1,2.5, q = 0.1),
    "band_offset": hp.quniform("b_offset",0.5,0.9,q=0.1),
    "smallWindow" : windowSmall
    }
     ])
 
    best = fmin(fn=run,
                space=param_space,
                algo=tpe.suggest,
                max_evals=1000)
                
    print ("Best parameters found: ", best)
    return best

def reset_globals():
    globals_dict = globals().copy()
    for key in globals_dict:
        del globals()[key]
        # if key == 'WINDOW_SIZE':
        #     continue
        # elif key == 'high_bollinger_band':
        #     globals()[key] = 1
        # elif key == 'low_bollinger_band':
        #     globals()[key] = 1
        # elif key == 'prev_sig':
        #     globals()[key] = -1 
        # elif type(value) == int: 
        #     globals()[key] = int(0) 
        # elif type(value) == list: 
        #     globals()[key] = list([])
        
    
def run(parm):
    global ratios
    global tick
    global profits
    
    for i in ratios:
        trade(i, parm)
        tick+=1
        #print(tick)
        
    temp_profits = profits
    
    # reset globals
    reset_globals()
    ###
    cum_profits = -np.sum(temp_profits)
    # if parm["name"] == "Bollis":
    #     print(parm["name"], cum_profits)
    return cum_profits

    
    
if __name__ == '__main__':
    
    
    datas = ["data/market_data1.csv", "data/market_data2.csv", "data/market_data3.csv", "data/market_data4.csv", "data/market_data6.csv"]
    
    #     #read in csv data
    # df = pd.read_csv(datas[0])

    # # create a new column to round time 
    # df['rounded_time'] = df.Time.round()

    # # filter dataframe to only keep relevant orders
    # df_relevant = df.loc[df['Operation']=='Insert', ['rounded_time', 'Instrument', 'Side','Volume','Price']]

    # # create a dictionary to store dataframes
    # tick_dict = {}

    # # iterate through rounded_time values
    # for t in df['rounded_time'].unique():
    #     # create temporary dataframe to store data
    #     df_temp = pd.DataFrame()
    #     # filter dataframe to only keep orders at given time t
    #     df_temp = df_relevant.loc[df['rounded_time']==t]

    #     df_0 = df_temp.loc[df_temp['Instrument'] == 0]
    #     # split dataframe into 'A' and 'B' orders
    #     df_A0 = df_0.loc[df_temp['Side']=='A']
    #     df_B0 = df_0.loc[df_temp['Side']=='B']
        
    #     # store dataframes in dictionary 
    #     tick_dict[t] = [df_0, df_B]

    # # print dictionary
    # price_vol_side = tick_dict
    
    # ratios = 
    
    # print(tick_dict)
    optimize_parameters()
    
