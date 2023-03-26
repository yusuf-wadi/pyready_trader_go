import asyncio
import itertools
from collections import deque
from typing import List
import time
import math
from ready_trader_go import BaseAutoTrader, Instrument, Lifespan, MAXIMUM_ASK, MINIMUM_BID, Side


LOT_SIZE = 50
POSITION_LIMIT = 100
TICK_SIZE_IN_CENTS = 100
MIN_BID_NEAREST_TICK = (MINIMUM_BID + TICK_SIZE_IN_CENTS) // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
MAX_ASK_NEAREST_TICK = MAXIMUM_ASK // TICK_SIZE_IN_CENTS * TICK_SIZE_IN_CENTS
AGGRESSIVENESS = 1.4
HISTORY_LENGTH = 3
WINDOW_SIZE = 4
#HEDGE_RATIO_MIN = 0  # Minimum hedge ratio (during low volatility)
#HEDGE_RATIO_MAX = 0.9  # Maximum hedge ratio (during high volatility)
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
        self.price_history = deque(maxlen=HISTORY_LENGTH)
        self.normalized_atr = 0
        self.last_hedge_time = time.time()
        self.etfPositon = 0
        self.futPostion = 0
        self.last_filled = -1
        self.rollingPrices = deque(maxlen=WINDOW_SIZE)
        self.mid_price = 0
        self.tick = 0

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
        """Called periodically to report the status of an order book.

        The sequence number can be used to detect missed or out-of-order
        messages. The five best available ask (i.e. sell) and bid (i.e. buy)
        prices are reported along with the volume available at each of those
        price levels.
        """
        self.logger.info("received order book for instrument %d with sequence number %d", instrument,
                         sequence_number)
        if instrument != Instrument.FUTURE:
            return
  
        if instrument == Instrument.FUTURE:
            #self.futPostion = self.position
            self.mid_price = (ask_prices[0] + bid_prices[0]) / 2
            self.price_history.append(self.mid_price)
            #self.rollingPrices.append(self.mid_price)
           
            atr = self.calculate_atr()
            self.normalized_atr = atr / (ask_prices[0] - bid_prices[0])
            dynamic_aggressiveness = int(AGGRESSIVENESS * self.normalized_atr) + 1
            #print(int(dynamic_aggressiveness))
            new_bid_price = bid_prices[0] - TICK_SIZE_IN_CENTS#int(TICK_SIZE_IN_CENTS * int(math.log(dynamic_aggressiveness**2)+1))
            new_ask_price = ask_prices[0] + TICK_SIZE_IN_CENTS#int(TICK_SIZE_IN_CENTS * int(math.log(dynamic_aggressiveness**2)+1))
            #print(dynamic_aggressiveness)
            min_lot_size = 50
            max_lot_size = 85
            adjusted_lot_size = min_lot_size + int((max_lot_size - min_lot_size) * math.log(self.normalized_atr,10) + 1)

            # self.movingAV = self.calc_rolling_av()
            # self.movingSD = self.calc_rolling_sd()
            
            if self.bid_id != 0 and new_bid_price not in (self.bid_price, 0):
                self.send_cancel_order(self.bid_id)
                self.bid_id = 0
            if self.ask_id != 0 and new_ask_price not in (self.ask_price, 0):
                self.send_cancel_order(self.ask_id)
                self.ask_id = 0
            
            if self.bid_id == 0 and new_bid_price != 0 and self.position + adjusted_lot_size < POSITION_LIMIT:
                self.bid_id = next(self.order_ids)
                self.bid_price = new_bid_price
                self.send_insert_order(self.bid_id, Side.BUY, new_bid_price, adjusted_lot_size, Lifespan.LIMIT_ORDER)
                self.bids.add(self.bid_id)
            if self.ask_id == 0 and new_ask_price != 0 and self.position - adjusted_lot_size > -POSITION_LIMIT:
                self.ask_id = next(self.order_ids)
                self.ask_price = new_ask_price
                self.send_insert_order(self.ask_id, Side.SELL, new_ask_price, adjusted_lot_size, Lifespan.LIMIT_ORDER)
                self.asks.add(self.ask_id)
            
           
            # # Adjust HEDGE_RATIO based on normalized ATR
            hedge_interval = int(min((10/(abs(dynamic_aggressiveness - 0.05)**7)),5))  # in seconds
            current_time = time.time()
            #hedge_vol = abs(abs(self.etfPositon) - abs(self.futPostion))
            cur_etf = self.etfPositon
            target = -cur_etf 
            pos_dif = target-self.futPostion
            hedge_p_scale = int(TICK_SIZE_IN_CENTS * 2 * math.log(dynamic_aggressiveness**3))
            #print(self.etfPositon, self.futPostion, self.last_filled)
            # add hedge_scale?
            if current_time - self.last_hedge_time > hedge_interval:
                if(pos_dif) > 0:
                    self.futPostion += abs(pos_dif)
                    self.send_hedge_order(next(self.order_ids), Side.BID, MAX_ASK_NEAREST_TICK ,abs(pos_dif))
                    self.last_hedge_time = time.time()
                if(pos_dif) < 0:
                    self.futPostion -= abs(pos_dif)
                    self.send_hedge_order(next(self.order_ids), Side.ASK,MIN_BID_NEAREST_TICK,  abs(pos_dif))
                    self.last_hedge_time = time.time()
                    
            

                
    def on_order_filled_message(self, client_order_id: int, price: int, volume: int) -> None:
        """Called when one of your orders is filled, partially or fully.

        The price is the price at which the order was (partially) filled,
        which may be better than the order's limit price. The volume is
        the number of lots filled at that price.
        """
        self.logger.info("received order filled for order %d with price %d and volume %d", client_order_id,
                         price, volume)
            # Calculate the ATR
        
        
        if client_order_id in self.bids:
            self.last_filled = 1
            self.position += volume
            self.etfPositon = self.position
            
        elif client_order_id in self.asks:
            self.last_filled = 0
            self.position -= volume
            self.etfPositon = self.position
            

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
        if instrument == Instrument.FUTURE:
            if (
                self.ask_id != 0
                and ask_prices[0] != 0
                and ask_prices[0] < self.ask_price
            ):
                self.send_cancel_order(self.ask_id)
                self.ask_id = 0

            if (
                self.bid_id != 0
                and bid_prices[0] != 0
                and bid_prices[0] > self.bid_price
            ):
                self.send_cancel_order(self.bid_id)
                self.bid_id = 0

    def calculate_atr(self) -> float:
        if len(self.price_history) < 2:
            return 0

        tr_values = []
        for i in range(1, len(self.price_history)):
            high = max(self.price_history[i], self.price_history[i - 1])
            low = min(self.price_history[i], self.price_history[i - 1])
            tr = high- low
            tr_values.append(tr)

        atr = sum(tr_values) / len(tr_values)
        return atr


    # def calc_rolling_av(self):
    #     sum = 0
    #     for i in range(1,len(self.rollingPrices)):
    #         sum += self.rollingPrices[i]
    #     return sum /WINDOW_SIZE

    # def calc_rolling_sd(self):
    #     sum = 0
    #     for i in range(1,len(self.rollingPrices)):
    #         sum += (self.rollingPrices[i] - self.movingAV) ** 2
    #     return math.sqrt(sum / (WINDOW_SIZE - 1))