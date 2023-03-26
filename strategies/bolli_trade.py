# Copyright 2021 Optiver Asia Pacific Pty. Ltd.
#
# This file is part of Ready Trader Go.
#
#     Ready Trader Go is free software: you can redistribute it and/or
#     modify it under the terms of the GNU Affero General Public License
#     as published by the Free Software Foundation, either version 3 of
#     the License, or (at your option) any later version.
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

from typing import List

from ready_trader_go import BaseAutoTrader, Instrument, Lifespan, MAXIMUM_ASK, MINIMUM_BID, Side


LOT_SIZE = 30
POSITION_LIMIT = 100
TICK_SIZE_IN_CENTS = 100
MIN_BID_NEAREST_TICK = (MINIMUM_BID + TICK_SIZE_IN_CENTS) // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
MAX_ASK_NEAREST_TICK = MAXIMUM_ASK // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
WINDOW_SIZE = 50
BAND_WIDTH = 2.5


class AutoTrader(BaseAutoTrader):

    
    def __init__(self, loop: asyncio.AbstractEventLoop, team_name: str, secret: str):
        """Initialise"""
        super().__init__(loop, team_name, secret)
        self.order_ids = itertools.count(1)
        self.bids = set()
        self.asks = set()
        self.ask_id = self.ask_price = self.bid_id = self.bid_price = self.position = 0
        self.midpoint_ETF = 1
        self.midpoint_FUTURE = 1
        self.ratios = []
        self.tick = 0
        self.SD = 0
        self.MA = 0
        self.high_bollinger_band = 1
        self.low_bollinger_band = 1
        self.next_message_id = 1
        self.max_ratio = float('-inf')
        self.min_ratio = float('inf')

    def on_error_message(self, client_order_id: int, error_message: bytes) -> None:
        """Called when the exchange detects an error.

        If the error pertains to a particular order, then the client_order_id
        will identify that order, otherwise the client_order_id will be zero.
        """
        self.logger.warning("error with order %d: %s", client_order_id, error_message.decode())
        if client_order_id != 0 and (client_order_id in self.bids or client_order_id in self.asks):
            self.on_order_status_message(client_order_id, 0, 0, 0)

    def on_hedge_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your hedge orders is filled.

        The price is the average price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        self.logger.info("received hedge filled for order %d with average price %d and volume %d", client_order_id,
                         price, volume)

    def on_order_book_update_message(self, instrument: int, sequence_number: int, ask_prices: List[int],
                                     ask_volumes: List[int], bid_prices: List[int], bid_volumes: List[int]) -> None:

        self.logger.info("received order book for instrument %d with sequence number %d", instrument,
                            sequence_number)
        self.logger.info("ask prices: %s", ask_prices[0])
        self.logger.info("ask volumes: %s", ask_volumes[0])
        self.logger.info("bid prices: %s", bid_prices[0])
        self.logger.info("bid volumes: %s", bid_volumes[0])
        
        self.set_midpoint(instrument, bid_prices[0], ask_prices[0])
        
        if instrument == Instrument.ETF:
            
            ratio = self.midpoint_ETF / self.midpoint_FUTURE
            self.logger.info("ratio: %f", ratio)
            
            # Check if current pair trading opportunity has expired.
            if self.ask_id != 0 and ratio <= 1:
                self.send_cancel_order(self.ask_id)
                self.logger.info("sell order %d cancelled", self.ask_id)
                self.ask_id = 0

            if self.bid_id != 0 and ratio >= 1:
                self.send_cancel_order(self.bid_id)
                self.logger.info("buy order %d cancelled", self.bid_id)
                self.bid_id = 0
            
            # Set the high/low bollinger bands.
            self.bollinger_bands(ratio)
            
            # Track the maximum and minimum ratio over a certain time period 
            if self.tick >= WINDOW_SIZE:
                
                # self.min_ratio = self.minRatio(self.ratios, self.min_ratio)
                # self.max_ratio = self.maxRatio(self.ratios, self.max_ratio)
                self.max_ratio = max(ratio, self.max_ratio)
                self.min_ratio = min(ratio, self.min_ratio)
                print(f'min ratio: {self.min_ratio}, max ratio: {self.max_ratio}\n low bol: {self.low_bollinger_band} high bol: {self.high_bollinger_band}')
                # Check if a pair trading opportunity exists.
                if self.bid_id == 0 and ratio < self.low_bollinger_band and ratio <= self.min_ratio and ratio < 1 and self.position < POSITION_LIMIT:
                    volume = LOT_SIZE
                    # Check position will not be exceeded
                    if self.position + volume >= POSITION_LIMIT:
                        volume = POSITION_LIMIT - abs(self.position)

                    self.bid_id = self.next_message_id
                    self.next_message_id += 1
                    self.send_insert_order(self.bid_id, Side.BUY, ask_prices[0], volume, Lifespan.GOOD_FOR_DAY)
                    self.logger.info("sending buy order %d bid price: %d", self.bid_id, self.midpoint_FUTURE)
                    self.bids.add(self.bid_id)
                
                if self.ask_id == 0 and ratio > self.high_bollinger_band and ratio >= self.max_ratio and ratio > 1 and self.position > -POSITION_LIMIT:
                    volume = LOT_SIZE
                    # Check position will not be exceeded
                    if self.position - volume <= -POSITION_LIMIT:
                        volume = POSITION_LIMIT - abs(self.position)

                    self.ask_id = self.next_message_id
                    self.next_message_id += 1
                    self.send_insert_order(self.ask_id, Side.SELL, bid_prices[0], volume, Lifespan.GOOD_FOR_DAY)
                    self.logger.info("sending sell order %d ask price: %d", self.ask_id, self.midpoint_FUTURE)
                    self.asks.add(self.ask_id)
                
                # reset min and max ratio
                self.max_ratio = float('-inf')
                self.min_ratio = float('inf')
            else:  
                self.tick+=1
    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:   
        """Called when one of your orders is filled, partially or fully.

        The price is the price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        #total_price = price * volume
        
        self.logger.info("received order filled for order %d with price %d and volume %d", client_order_id,
                         price, volume)
        if client_order_id in self.bids:
            self.position += volume
            
            self.send_hedge_order(self.next_message_id, Side.SELL, MIN_BID_NEAREST_TICK, volume)
            self.next_message_id += 1
            
        elif client_order_id in self.asks:
            self.position -= volume
            
            self.send_hedge_order(self.next_message_id, Side.BUY, MAX_ASK_NEAREST_TICK, volume)
            self.next_message_id += 1

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
    def maxRatio(self, ratios, cur_max):
        for i in ratios:
            if i > cur_max:
                cur_max = i
        return cur_max
    
    def minRatio(self, ratios, cur_min):
        for i in ratios:
            if i < cur_min:
                cur_min = i
        return cur_min

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

    def bollinger_bands(self, ratio):
        """
        ### a common technical indicator:
        
        Bollinger Bands consist of three lines: a moving average (usually a simple moving average) that represents the average price of the instrument,
        an upper band that is a certain number of standard deviations above the moving average, and a lower band that is a certain number of standard deviations below the moving average.
        The standard deviation is a measure of how much the price varies from the average.

        Bollinger Bands can be used to generate trading signals based on various rules, such as when the price touches or crosses one of the bands, when the bands widen or narrow, when the price moves above or below the moving average, etc. Different traders may use different settings for Bollinger Bands depending on their preferences and strategies34
        """ 
        sum = 0
        boll_window = 50
        if len(self.ratios) < boll_window:
            self.ratios.append(ratio)
            #print(self.ratios)
        else:
            self.ratios.pop(0)
            self.ratios.append(ratio)

            # Calculate the moving average.
            sum = 0
            for i in range(boll_window):
                sum += self.ratios[i]
            self.MA = sum / boll_window

            # Calculate the moving standard deviation.
            sum = 0
            for i in range(boll_window):
                sum += math.pow(self.ratios[i] - self.MA, 2)
            self.SD = math.sqrt(sum / boll_window)

            # Set the bollinger band.
            self.high_bollinger_band = self.MA + BAND_WIDTH * self.SD
            self.low_bollinger_band = self.MA - BAND_WIDTH * self.SD
        
