import threading
import time
from datetime import datetime
from itertools import chain
from sys import argv
from threading import Thread
from pymongo import MongoClient
from dbrecord import Trading
from marketcap import Marketcap
from publicdef import subscribetype, Ordertype, Currency, Price
from suona import sms
from trade_cnbtc import trade_cnbtc
from trade_test import trade_test

PRE_SALE_PRICE_PER = 1.005

class strategy_ma:
    # {"_id":ObjectId("58be4f346e4a4e322916bdce"),
    # strategy_type":2,
    # 'price': 1000,
    # "currency_type": 2,
    #  config: {"upline": [{"unit": 15, "range": 5}, {"unit": 15, "range": 10}],
    #           "downline": [{"unit": 15, "range": 30}]}
    # }

    __strategy_config = None
    __capture = None
    __trader = None

    if 'debug' in argv:
        __trader = trade_test()
    else:
        __trader = trade_cnbtc()

    __trade_db = Trading()
    # {'strategy_id': ObjectId("58be4f346e4a4e322916bdce")
    #   hold_count': 0.0,
    #   'price': 0.0,
    #   'order': {'on_sale': [{'id': 111, count:100, price:107.3, ticket:188377}], 'on_purchase': [{'id': 111}] ,
    #               'last_sale_ticket':000000, 'last_purchase_ticket':00000,'last_sale_price':90, 'last_purchase_price':90}l
    # }
    __running_status_lock = threading.RLock()
    __running_status = None

    __upline_data = {}
    __downline_data = {}
    __db_collection = None
    __fresh_close_price = Price()
    __strategy_action_msg = None
    __fresh_macd_price = None

    __strategy_decide = None
    __ma_decide = None
    __macd_decide = None

    up_level_1 = 0.0
    up_level_2 = 0.0
    down_max_value = 0.0

    def __init__(self):
        dbClient = MongoClient('mongodb://localhost:27017')
        db = dbClient['tcTrader']
        self.__db_collection = db['TraderConfig']
        pass

    def set_strateg_config(self, config):
        self.__strategy_config = config
        return True

    def set_market_capture(self, capture: Marketcap):
        self.__capture = capture
        return

    def start_running(self):
        if self.__strategy_config is None or self.__capture is None:
            return False

        self.get_running_status_from_db()
        if self.__running_status['order'].get('on_sale', []):
            self.__strategy_decide = Ordertype.Sale
        elif self.__running_status['order'].get('on_purchase', []):
            self.__strategy_decide = Ordertype.Purchase
            self.__macd_decide = self.__strategy_decide
            self.__ma_decide = self.__strategy_decide

        param = {'currencytype': self.__strategy_config['currency_type']}
        self.__capture.setparam(param)
        for item in chain(self.__strategy_config['config'].get('upline', []),
                          self.__strategy_config['config'].get('downline', [])):
            if 'unit' in item and 'range' in item:
                param = {'subscribes': {'type': subscribetype.maprice,
                                        'func': self.push_ma_price,
                                        'params': {'maunit': item['unit'], 'marange': item['range']}}}
                self.__capture.setparam(param)
        param = {'subscribes': {'type': subscribetype.macd,
                               'func': self.push_macd_price,
                               'params': {'unit': 15}}}
        self.__capture.setparam(param)
        if 'debug' in argv:
            self.test_update_order_to_trader()

        t = Thread(target=self.tracking_order_status)
        t.start()

        self.print_running_status()
        pass

    #macd is dic
    #{ticket:00000, dif:-0.11, dea:-0.22, bar:0.22, fresh_price()}
    def push_macd_price(self, macd):

        if macd['bar'] is None:
            return

        self.__fresh_macd_price = macd

        decide = None
        needs_sale = False

        if macd['bar'] > 0.0:
            decide = Ordertype.Purchase
        elif macd['bar'] < 0.0:
            decide = Ordertype.Sale
        if decide is None:
            return

        if self.__macd_decide == self.__strategy_decide and decide != self.__macd_decide:
            needs_sale = True
            if macd['bar'] < -0.2:
                self.__strategy_decide = decide
                self.__macd_decide = decide
                self.__ma_decide = None
        elif self.__strategy_decide == decide:
            self.__macd_decide = decide

        if self.__macd_decide is not None or needs_sale:
            fresh_price = Price()
            fresh_price.from_dict(macd.get('fresh_price', {}))
            if self.__strategy_decide == Ordertype.Sale or needs_sale:
                self.execute_sale(fresh_price)
            elif self.__strategy_decide == Ordertype.Purchase:
                self.execute_purchase(fresh_price)

            self.__strategy_action_msg = \
            ("Nothing to do" if self.__strategy_decide is None else str(self.__strategy_decide)) + " Decide by (MACD)"

            # self.__strategy_action_msg = ("Nothing to do" if self.__strategy_decide is None else str(self.__strategy_decide)) + \
            #                                                             " MA({},{},{})".format(round(up_level_1, 2),
            #                                                                                   round(up_level_2, 2),
            #                                                                                   round(down_max_value, 2))

        return

    def push_ma_price(self, ma_price):

        # self.make_order_notify(Ordertype.Sale, 220.22222, 111.11111)

        self.__fresh_close_price = ma_price.fresh_price
        tup = (ma_price.unit, ma_price.period)
        if tup in self.__downline_data:
            self.__downline_data[tup] = ma_price
        elif tup in self.__upline_data:
            self.__upline_data[tup] = ma_price
        else:
            return

        all_data = dict(self.__downline_data.items() | self.__upline_data.items())
        if None in all_data.values():
            return

        max_ticket = max(all_data.values(), key=lambda x: x.ticket)
        min_ticket = min(all_data.values(), key=lambda x: x.ticket)

        if max_ticket.ticket - min_ticket.ticket > 15:
            return

        # 买入判断

        # up_min_value = min(self.__upline_data.values(), key=lambda x: x.close_price).close_price
        # up_max_value = max(self.__upline_data.values(), key=lambda x: x.close_price).close_price

        list_upline = sorted(self.__upline_data.items(), key=lambda x: x[0][1])
        self.up_level_1 = list_upline[0][1].close_price
        self.up_level_2 = list_upline[1][1].close_price

        self.down_max_value = max(self.__downline_data.values(), key=lambda x: x.close_price).close_price
        # down_min_value = min(self.__downline_data.values(), key=lambda x: x.close_price).close_price

        action = None
        if self.up_level_1 > self.up_level_2 > self.down_max_value:
            if time.time() - max_ticket.ticket/1000.0 < 300:
                # self.execute_purchase(ma_price.fresh_price)
                action = Ordertype.Purchase
        elif (self.up_level_2 > self.down_max_value > self.up_level_1 and self.up_level_2 - self.up_level_1 < self.down_max_value * 0.01) is False \
                and ma_price.fresh_price.last <= self.down_max_value:
            # self.execute_sale(ma_price.fresh_price)
            action = Ordertype.Sale

        if self.__ma_decide == self.__strategy_decide and action != self.__ma_decide:
            self.__strategy_decide = action
            self.__ma_decide = action
            self.__macd_decide = None
        elif self.__strategy_decide == action:
            self.__ma_decide = action

        if self.__ma_decide is not None and action is not None:
            if self.__strategy_decide == Ordertype.Sale:
                self.execute_sale(ma_price.fresh_price)
            elif self.__strategy_decide == Ordertype.Purchase:
                self.execute_purchase(ma_price.fresh_price)

            self.__strategy_action_msg = \
            ("Nothing to do" if self.__strategy_decide is None else str(self.__strategy_decide)) + " Decide by (MA)"
        return

    def tracking_order_status(self):
        while 1:
            if self.__running_status is None:
                time.sleep(1)
                continue

            with self.__running_status_lock:
                self.tracking_order_by_orderinfo(self.__running_status['order']['on_sale'], 1)
                self.tracking_order_by_orderinfo(self.__running_status['order']['on_purchase'], 2)

                if (not self.__running_status['order']['on_sale']) and \
                        self.__running_status['hold_count'] and \
                        (not self.__running_status['order']['on_purchase']) and \
                                self.__running_status['order'].get('last_purchase_price', None) is not None:
                    self.quickly_pre_sale(self.__running_status['order']['last_purchase_price'] * PRE_SALE_PRICE_PER)

            time.sleep(2)
        return

    def tracking_order_by_orderinfo(self, order_list, ordertype):
        for order_info in order_list:
            order_status = self.__trader.getorderlist(Ordertype(ordertype), 0, order_info['id'],
                                                   Currency(self.__strategy_config['currency_type']))
            if order_status._totalcount != 0.0 and \
                                    order_status._totalcount - order_status._acceptcount != order_info['count']:
                self.order_change_status(order_status)
        return

    def order_change_status(self, orderinfo):
        order_type_str = None
        if Ordertype.Sale == orderinfo._type:
            order_type_str = 'on_sale'
        elif Ordertype.Purchase == orderinfo._type:
            order_type_str = 'on_purchase'

        if order_type_str == None:
            return
        with self.__running_status_lock:
            order_idx = None
            try:
                order_idx = next(idx for (idx, order_info) in enumerate(self.__running_status['order'][order_type_str]) if order_info['id'] == orderinfo._id)
            except StopIteration:
                print(self.__running_status['order'][order_type_str])

            if order_idx != None:
                new_left_count = orderinfo._totalcount - orderinfo._acceptcount
                old_lef_count = self.__running_status['order'][order_type_str][order_idx]['count']
                if new_left_count != old_lef_count:
                    self.__running_status['order'][order_type_str][order_idx]['count'] = new_left_count
                    if Ordertype.Sale == orderinfo._type:
                        self.__running_status['price'] += \
                            (old_lef_count - new_left_count) * self.__running_status['order'][order_type_str][order_idx]['price']
                    elif Ordertype.Purchase == orderinfo._type:
                        self.__running_status['hold_count'] += old_lef_count - new_left_count

                    # 产生交易记录
                    trade_record = {'time': time.time(),
                                    'order_id': orderinfo._id,
                                    'strategy_id': self.__running_status['strategy_id'],
                                    'trade_type': orderinfo._type.value,
                                    'vol': old_lef_count - new_left_count,
                                    'price': self.__running_status['order'][order_type_str][order_idx]['price'],
                                    'cost_price': 0}
                    self.__trade_db.deal_order(trade_record)

                    if new_left_count == 0:
                        deal_order = self.__running_status['order'][order_type_str].pop(order_idx)
                        if Ordertype.Sale == orderinfo._type and \
                                        self.__running_status['price'] > self.__strategy_config['price'] * 1.1:
                            self.__running_status['in_pocket'] = self.__running_status['price'] - self.__strategy_config['price']
                            self.__running_status['price'] = self.__strategy_config['price']

                        #成交后马上下卖单
                        if Ordertype.Purchase == orderinfo._type:
                            self.quickly_pre_sale(deal_order['price'] * PRE_SALE_PRICE_PER)
                            # self.__strategy_decide = Ordertype.Sale
                            # self.__macd_decide = Ordertype.Purchase
                            # self.__ma_decide = Ordertype.Purchase
                            # price = deal_order['price'] * 1.005
                            # self.execute_sale(Price(price, price, price))
                            # self.__strategy_action_msg = str(self.__strategy_decide) + " Decide by 快速止盈"

                    self.update_running_status_to_db()
        return

    def update_running_status_to_db(self, upsert =False):
        self.__db_collection.update({'strategy_id': self.__strategy_config['_id']},
                                    self.__running_status,
                                    upsert)
        return

    def execute_sale(self, price):
        # TODO 取消所有买单
        now_ticket = time.time()
        # 若卖单超过60秒未成交
        # 并且当前价格低于委托价格1个点，则撤销订单并按当前买一价重新挂单
        with self.__running_status_lock:
            retrade_orders = list(filter(lambda x: now_ticket - x['ticket'] >= 60 and price.last < x['price']*0.97,
                                         self.__running_status['order']['on_sale']))
            for order_info in retrade_orders:
                if self.__trader.cancelorder(order_info['id'], Currency(self.__strategy_config['currency_type'])):
                    self.__running_status['hold_count'] += (order_info['count'] / (1.0 -0.0005))
                    self.__running_status['order']['on_sale'].remove(order_info)
                    self.update_running_status_to_db()

            sale_count = self.__running_status.get('hold_count', 0)

            # 买单下单15分钟内,若下跌不超过2%,则忽视卖出操作
            if now_ticket - self.__running_status['order'].get('last_purchase_ticket', 0) < 30*60 and \
                    self.__running_status['order'].get('last_purchase_price', 0.0) * 0.98 > price.last:
                sale_count = 0

            if sale_count <= 0.0:
                return

            sale_count = (1.0 - 0.0005) * sale_count
            new_order_id = self.__trader.makeoder(price.buy,
                                                   Ordertype.Sale,
                                                   sale_count,
                                                   Currency(self.__strategy_config['currency_type']))
            if new_order_id != 0:
                self.__running_status['hold_count'] = 0
                self.__running_status['order']['on_sale'].append({'id': new_order_id,
                                                         'count': sale_count,
                                                         'price': price.buy,
                                                         'ticket': time.time()})
                self.update_running_status_to_db()
                self.__running_status['order'].update({'last_sale_ticket': now_ticket})
                self.__running_status['order'].update({'last_sale_price': price.buy})
                # notifyer = sms()
                # notifyer.notify_make_order(Ordertype.Sale, price.last, sale_count)

                self.make_order_notify(Ordertype.Sale, price.last, sale_count)

        return

    def execute_purchase(self, price):

        with self.__running_status_lock:
            # 取消所有卖单
            # sale_orders = self.__running_status['order'].get('on_sale', [])
            # if sale_orders:
            #     for order in sale_orders:
            #         cancel_item = None
            #         if self.__trader.cancelorder(order['id'], Currency(self.__strategy_config['currency_type'])) != 0:
            #             self.__running_status['hold_count'] += (order['count'] / (1.0 - 0.0005))
            #             cancel_item = order
            #             self.__running_status['order']['on_sale'].remove(order)
            #             self.update_running_status_to_db()
            #         if cancel_item:
            #             self.quickly_pre_sale(cancel_item['price'] * PRE_SALE_PRICE_PER)
            #             # self.__strategy_decide = Ordertype.Sale
            #             # self.__macd_decide = Ordertype.Purchase
            #             # self.__ma_decide = Ordertype.Purchase
            #             # price = cancel_item['price'] * 1.006
            #             # self.execute_sale(Price(price, price, price))
            #             # self.__strategy_action_msg = str(self.__strategy_decide) + " Decide by 快速止盈"
            #     return


            # 若买单超过60秒未成交
            # 并且当前价格高于委托价格8个点，则撤销订单并按当前买一价重新挂单
            now_ticket = time.time()
            retrade_orders = list(filter(lambda x: now_ticket - x['ticket'] >= 60 and price.buy * 0.92 > x['price'],
                                         self.__running_status['order']['on_purchase']))
            for order_info in retrade_orders:
                if self.__trader.cancelorder(order_info['id'], Currency(self.__strategy_config['currency_type'])):
                    self.__running_status['price'] += (order_info['count'] * order_info['price'])  # / (1.0 - 0.0005)
                    self.__running_status['order']['on_purchase'].remove(order_info)
                    self.update_running_status_to_db()

            if self.__running_status.get('price', 0) < 1:
                return


            # buy_price = (price.high + price.low)/2
            # if buy_price < 1.0:

            if self.up_level_1 == 0.0 or self.up_level_2 == 0.0 or self.down_max_value == 0.0:
                return

            buy_price = price.buy * 0.996
            max_ma_value = max([self.up_level_1, self.up_level_2, self.down_max_value])
            if buy_price > max_ma_value > 0:
                buy_price = max_ma_value

            buy_count = round(self.__running_status['price']/buy_price, 2)
            new_order_id = self.__trader.makeoder(buy_price,
                                                  Ordertype.Purchase,
                                                  buy_count,
                                                  Currency(self.__strategy_config['currency_type']))
            if new_order_id != 0:
                self.__running_status['price'] = 0
                self.__running_status['order']['on_purchase'].append({'id': new_order_id,
                                                             'count': buy_count,
                                                             'price': buy_price,
                                                             'ticket': time.time()})
                self.__running_status['order'].update({'last_purchase_ticket': time.time()})
                self.__running_status['order'].update({'last_purchase_price': buy_price})
                self.update_running_status_to_db()
                # notifyer = sms()
                # notifyer.notify_make_order(Ordertype.Purchase, price.last, buy_count)
                self.make_order_notify(Ordertype.Purchase, buy_price, buy_count)
        return

    def get_running_status_from_db(self):
        running_status = self.__db_collection.find({"strategy_id": self.__strategy_config['_id']})
        if running_status.count() < 1:
            # 第一次执行
            self.__running_status = {'strategy_id': self.__strategy_config['_id'],
                                     'hold_count': 0.0,
                                     'price': self.__strategy_config['price'],
                                     'order': {'on_sale': [], 'on_purchase': []}}
            self.update_running_status_to_db(True)
        else:
            self.__running_status = running_status[0]

        for line_info in self.__strategy_config['config']['upline']:
            tup = (line_info['unit'], line_info['range'])
            self.__upline_data[tup] = None
        for line_info in self.__strategy_config['config']['downline']:
            tup = (line_info['unit'], line_info['range'])
            self.__downline_data[tup] = None
        return

    def test_update_order_to_trader(self):
        for item in chain(self.__running_status['order']['on_sale'],
                          self.__running_status['order']['on_purchase']):
            order_info = {item['id']: {'count': item['count'], 'price': item['price']}}
            self.__trader.add_order(order_info)

        param = {'subscribes': {'type': subscribetype.realprice,
                                'func': self.__trader.push_rt_price}
                 }

        self.__capture.setparam(param)

        return

    def get_breakeven(self, start_time=0, stop_time=0):
        principal = self.__strategy_config['price']
        accout_amount = self.__running_status['price']

        if self.__fresh_close_price.last == 0.0:
            return None

        accout_amount += (self.__running_status['hold_count'] * self.__fresh_close_price.last)
        for item in self.__running_status['order']['on_sale']:
            accout_amount += (item['count'] * self.__fresh_close_price.last)
        for item in self.__running_status['order']['on_purchase']:
            accout_amount += (item['count'] * item['price'])
        return accout_amount - principal + self.__running_status.get('in_pocket', 0.0)

    def get_hold_bc_count(self):
        bc_amount = 0.0
        bc_amount += self.__running_status['hold_count']
        for item in self.__running_status['order']['on_sale']:
            bc_amount += item['count']
        return bc_amount

    def print_running_status(self):
        print("[%s] total revenue:%s hold_bc:%f fresh_price:%.2f MACD:(dif:%.2f, dea:%.2f, bar:%.2f)" %
              ('{0:%Y-%m-%d %H:%M:%S}'.format(datetime.now()),
               '¥'+str(round(self.get_breakeven(), 2)) if  self.get_breakeven() != None else 'waiting for market price',
               self.get_hold_bc_count(),
               self.__fresh_close_price.last,
               (self.__fresh_macd_price['dif'] if self.__fresh_macd_price else 0.0),
               (self.__fresh_macd_price['dea'] if self.__fresh_macd_price else 0.0),
               (self.__fresh_macd_price['bar'] if self.__fresh_macd_price else 0.0)) + \
              "MA({},{},{})".format(round(self.up_level_1, 2), round(self.up_level_2, 2), round(self.down_max_value, 2))
              + " {}".format(self.__strategy_action_msg))

        threading.Timer(15, self.print_running_status).start()
        return

    def make_order_notify(self, optype, price, amount):
        notifyer = sms()
        accout_info = self.__trader.getaccountasset()
        total_assets = 0.0
        if accout_info:
            total_assets = accout_info['cny'].get('total', 0.0)
            total_assets += (accout_info['eth'].get('total', 0.0) * self.__fresh_close_price.last)

        return notifyer.notify_make_order_with_assets(optype, price, amount, total_assets)

    def quickly_pre_sale(self, price):
        self.__strategy_decide = Ordertype.Sale
        self.__macd_decide = Ordertype.Purchase
        self.__ma_decide = Ordertype.Purchase
        # price = cancel_item['price'] * 1.006
        self.execute_sale(Price(price, price, price))
        self.__strategy_action_msg = str(self.__strategy_decide) + " Decide by 快速止盈"
        return
