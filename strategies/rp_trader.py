    
# Copyright 2021 Optiver Asia Pacific Pty. Ltd.
#
# This file is part of Ready Trader Go.
#
#     Ready Trader Go is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public License
#     as published by the Free Software Foundation, either veself.rsion 3 of
#     the License, or (at your option) any later veself.rsion.
#
#     Ready Trader Go is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU Affero General Public License for more details.
#
#     You should have received a copy of the GNU Affero General Public
#     License along with Ready Trader Go.  If not, see
#     <https://www.gnu.org/licenses/>.
import asyncio
import itertools
import math
import numpy as np
from typing import List

from ready_trader_go import BaseAutoTrader, Instrument, Lifespan, MAXIMUM_ASK, MINIMUM_BID, Side



LOT_SIZE = 20
POSITION_LIMIT = 100
TICK_SIZE_IN_CENTS = 100
MIN_BID_NEAREST_TICK = (MINIMUM_BID + TICK_SIZE_IN_CENTS) // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
MAX_ASK_NEAREST_TICK = MAXIMUM_ASK // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS


class AutoTrader(BaseAutoTrader):
    """Example Auto-trader.
    When it starts this auto-trader places ten-lot bid and ask orders at the
    current best-bid and best-ask prices respectively. Thereafter, if it has
    a long position (it has bought more lots than it has sold) it reduces its
    bid and ask prices. Conversely, if it has a short position (it has sold
    more lots than it has bought) then it increases its bid and ask prices.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, team_name: str, secret: str):
        """Initialise a new instance of the AutoTrader class."""
        super().__init__(loop, team_name, secret)
        self.order_ids = itertools.count(1)
        self.bids = set()
        self.asks = set()
        self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = 0
        self.window = 110
        self.rsi = []
        self.rsi_window = 13
        self.stoch_rsi = 0
        self.movingAverage = 0
        self.movingSD = 0
        self.currentETF = 0
        self.currentFutures = 0
        self.currentRatio = 0
        self.rollingPrices = list()
        self.tick = 0
        self.best_bids = []
        self.best_asks = []

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.
        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        self.logger.warning("error with order %d: %s", client_order_id, error_message.decode())
        if client_order_id != 0:
            self.on_order_status_message(client_order_id, 0, 0, 0)

    def on_hedge_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your hedge orders is filled, partially or fully.
        The price is the average price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        If the order was unsuccessful, both the price and volume will be zero.
        """
        self.logger.info("received hedge filled for order %d with average price %d and volume %d", client_order_id,
                         price, volume)


    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically to report the status of an order book.
        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """
        self.logger.info("received order book for instrument %d with sequence number %d", instrument,
                         sequence_number)

        # ratio
        if instrument == Instrument.ETF:
            self.currentETF = (bid_prices[0] + ask_prices[0]) / 2
            if self.currentFutures == 0 or self.currentETF == 0:
                return
        if instrument == Instrument.FUTURE:
            #self.currentFutures = (bid_prices[0] + ask_prices[0]) / 2
            self.currentFutures = (bid_prices[0] + ask_prices[0]) / 2
            if self.currentFutures == 0 or self.currentETF == 0:
                return
        self.rollingPrices.append(self.currentRatio)
        
    
        
        
        self.currentRatio = self.currentETF / self.currentFutures
        #self.currentRatio = self.currentFutures / self.currentETF
        
        if instrument == Instrument.FUTURE:
            self.best_bids.append(bid_prices[0])
            self.best_asks.append(ask_prices[0])
            if self.tick > 5:
                pt_flu = abs(self.rollingPrices[-2] - self.rollingPrices[-3])/self.rollingPrices[-2]
                self.best_bids.pop(0)
                self.best_asks.pop(0)
                bid_quote = np.sum(bid_volumes)
                ask_quote = np.sum(ask_volumes)
                tick_size = 100
                if (bid_quote or ask_quote) == 0:
                    return
                # Ask Order Price
                if(((bid_quote - ask_quote) / (bid_quote + ask_quote)) > 0.5):
                    new_ask_price = self.best_asks[-1] + (abs(self.best_asks[-1] - self.best_asks[-2]) + 2) * tick_size

                elif(((ask_quote - bid_quote) / (bid_quote + ask_quote))> 0.5):
                    new_ask_price = self.best_asks[-1] + (abs(self.best_asks[-1] - self.best_asks[-2])) * tick_size

                else:
                    new_ask_price = self.best_asks[-1] + (abs(self.best_asks[-1] - self.best_asks[-2]) + 1) * tick_size

                # Bid Order Price
                if(((bid_quote - ask_quote) / (bid_quote + ask_quote)) > 0.5):
                    new_bid_price = self.best_bids[-1] - (abs(self.best_bids[-1] - self.best_bids[-2])) * tick_size

                elif(((ask_quote - bid_quote) / (bid_quote + ask_quote))> 0.5):
                    new_bid_price = self.best_bids[-1] - (abs(self.best_bids[-1] - self.best_bids[-2]) + 2) * tick_size

                else:
                    new_bid_price = self.best_bids[-1] - (abs(self.best_bids[-1] - self.best_bids[-2]) + 1) * tick_size
                
                if self.tick >= self.window:
                    self.rsi_window = 13
                    self.window = 110
                    
                    self.movingAverage = self.calculate_rolling_average_50()
                    self.movingSD = self.calculate_rolling_sd_50()
                    if self.movingSD != 0:
                        Z = (self.currentRatio - self.movingAverage) / self.movingSD
                
                    self.calc_stochastic_rsi()
                    #print(f'rsi: {self.rsi}')
                    #self.logger.
                    #price_adjustment = - (self.position // LOT_SIZE) * TICK_SIZE_IN_CENTS
                    

                    if self.bid_id != 0 and new_bid_price not in (self.bid_price, 0):
                        self.send_cancel_order(self.bid_id)
                        self.bid_id = 0
                        return
            
                    if self.ask_id != 0 and new_ask_price not in (self.ask_price, 0):
                        self.send_cancel_order(self.ask_id)
                        self.ask_id = 0
                        return
                    print(f'z: {Z}\nstochRSI: {self.stoch_rsi}')
                    Zh = 1.005
                    Zl = 0.995
                    SRh = 0.55
                    SRl = 0.45
                    
                    if Z > Zh and self.stoch_rsi > SRh:  # sell in pos
                        if self.ask_id == 0 and new_ask_price != 0 and self.position - LOT_SIZE> -POSITION_LIMIT:   
                            self.ask_id = next(self.order_ids)
                            self.ask_price = new_ask_price
                            self.send_insert_order(self.ask_id, Side.SELL, new_ask_price, LOT_SIZE, Lifespan.G)
                            self.asks.add(self.ask_id)
                    elif Z < Zl and self.stoch_rsi < SRl:  # buy in pos
                        if self.bid_id == 0 and new_bid_price != 0 and self.position + LOT_SIZE < POSITION_LIMIT:
                            self.bid_id = next(self.order_ids)
                            self.bid_price = new_bid_price
                            self.send_insert_order(self.bid_id, Side.BUY, new_bid_price, LOT_SIZE, Lifespan.G)
                            self.bids.add(self.bid_id)
                    else:
                        self.rsi_window = 4
                        self.window = 10
                        
                        self.calc_stochastic_rsi()
                        self.movingAverage = self.calculate_rolling_average_50()
                        self.movingSD = self.calculate_rolling_sd_50()
                        Z = (self.currentRatio - self.movingAverage) / self.movingSD
                        
                        if Z > Zh and self.stoch_rsi > SRh:  # sell in pos
                            if self.ask_id == 0 and new_ask_price != 0 and self.position - LOT_SIZE> -POSITION_LIMIT:
                                self.ask_id = next(self.order_ids)
                                self.ask_price = new_ask_price
                                self.send_insert_order(self.ask_id, Side.SELL, new_ask_price, LOT_SIZE, Lifespan.G)
                                self.asks.add(self.ask_id)
                        elif Z < Zl and self.stoch_rsi < SRl:  # buy in pos
                            if self.bid_id == 0 and new_bid_price != 0 and self.position + LOT_SIZE < POSITION_LIMIT:
                                self.bid_id = next(self.order_ids)
                                self.bid_price = new_bid_price
                                self.send_insert_order(self.bid_id, Side.BUY, new_bid_price, LOT_SIZE, Lifespan.G)
                                self.bids.add(self.bid_id)
                        

        self.tick += 1

    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when when of your orders is filled, partially or fully.
        The price is the price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        self.logger.info("received order filled for order %d with price %d and volume %d", client_order_id,
                         price, volume)
        if client_order_id in self.bids:
            self.position += volume
            self.send_hedge_order(next(self.order_ids), Side.ASK, MIN_BID_NEAREST_TICK, volume)
        elif client_order_id in self.asks:
            self.position -= volume
            self.send_hedge_order(next(self.order_ids), Side.BID,
                                  MAX_ASK_NEAREST_TICK, volume)

    def on_order_status_message(self, client_order_id: int, fill_volume: int, remaining_volume: int,
                                fees: int) -> None:
        """Called when the status of one of your orders changes.
        The fill_volume is the number of lots already traded, remaining_volume
        is the number of lots yet to be traded and fees is the total fees for
        this order. Remember that you pay fees for being a market taker, but
        you receive fees for being a market maker, so fees can be negative.
        If an order is cancelled its remaining volume will be zero.
        """
        self.logger.info("received order status for order %d with fill volume %d remaining %d and fees %d",
                         client_order_id, fill_volume, remaining_volume, fees)
        if remaining_volume == 0:
            if client_order_id == self.bid_id:
                self.bid_id = 0
            elif client_order_id == self.ask_id:
                self.ask_id = 0

            # It could be either a bid or an ask
            self.bids.discard(client_order_id)
            self.asks.discard(client_order_id)

    def on_trade_ticks_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                               ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:
        """Called periodically when there is trading activity on the market.
        The five best ask (i.e. sell) and bid (i.e. buy) prices at which there
        has been trading activity are reported along with the aggregated volume
        traded at each of those price levels.
        If there are less than five prices on a side, then zeros will appear at
        the end of both the prices and volumes arrays.
        """
        self.logger.info("received trade ticks for instrument %d with sequence number %d", instrument,
                         sequence_number)
        
    
    def calculate_rolling_average_50(self):
        sum = 0
        if len(self.rollingPrices) > self.window:
            for i in range(self.tick -self.window, self.tick-1):
                sum += self.rollingPrices[i]
        return sum /self.window

    def calculate_rolling_sd_50(self):
        sum = 0
        if len(self.rollingPrices) > self.window:
            for i in range(self.tick -self.window, self.tick-1):
                sum += (self.rollingPrices[i] - self.movingAverage) ** 2
        return math.sqrt(sum / (self.window - 1))
    
    def set_midpoint(self, instrument: int, bid_price: int, ask_price: int):
        
        # Check for undefined division.
        if bid_price == 0 or ask_price == 0:
            print(0)
            
        else:
            #print(bid_price, ask_price)
            if instrument == Instrument.FUTURE:
                self.midpoint_FUTURE = (ask_price + bid_price) / 2
                if self.midpoint_FUTURE % 100 != 0:
                    self.midpoint_FUTURE += 50
                #print(self.midpoint_FUTURE + "mid futures")
            
            if instrument == Instrument.ETF:
                self.midpoint_ETF = (ask_price + bid_price) / 2
                if self.midpoint_ETF % 100 != 0:
                    self.midpoint_ETF += 50
    def calc_rsi(self):
    # Calculate the rsi
        if len(self.rollingPrices) > self.rsi_window:
            diff = np.diff(self.rollingPrices[-self.rsi_window:])
            up = np.sum(diff[diff>=0])
            down = np.sum(-diff[diff<0])
            rs = up/down if down != 0 else 0
            nRSI = 100 - (100 / (1 + rs))
            self.rsi.append(nRSI)
        else:
            self.rsi = 50
                      
    def calc_stochastic_rsi(self):
        # Calculate the stochastic RSI
        self.calc_rsi()
        stoch_window = self.rsi_window 
        
        if len(self.rollingPrices) > self.rsi_window:
            rsi_range = np.max(self.rsi[-stoch_window:]) - np.min(self.rsi[-stoch_window:])
            if rsi_range != 0:
                stoch_rsi = (self.rsi[-1] - np.min(self.rsi[-stoch_window:])) / rsi_range
            else:
                stoch_rsi = 0
            self.stoch_rsi = stoch_rsi
        else:
            self.stoch_rsi = 0
        