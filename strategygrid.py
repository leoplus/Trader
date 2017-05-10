
import threading
from pymongo import MongoClient
import marketcap
from dbrecord import Trading
from publicdef import Price, Currency, Ordertype
from trade_cnbtc import trade_cnbtc
import time
from trade_test import trade_test




class strategy_grid:
    __strateg_name = "网格策略"
    __strateg_config = {}
    __maprices = {}
    __mapricesupdatetime = 0
    #__trader = trade_cnbtc()
    __trader = trade_test()

    # {strategy_id:object_id,
    # grid_lines: [{grid_idx:1, purchase_price: 0.0,sale_price:0.0,,count:10,quota:0,break_even:0.0,
    #   onsale_order:{orderid:{count':1.0,'price':0.0,cost_price:10.7},orderid:{count:1.0}},onpurchase_order:{}}
    __grid_running_status = {}
    __db_collection = 0
    #Tracking unsettled order id list
    # {'id':type}
    __tracking_orders = {}
    __fresh_price = Price()
    __trade_db = Trading()

    def __init__(self):
        dbClient = MongoClient('mongodb://localhost:27017')
        db = dbClient['tcTrader']
        self.__db_collection = db['TraderConfig']
        return

    def set_strateg_config(self, config):
        self.__strateg_config = config

    def set_market_capture(self, capture: marketcap.Marketcap):
        prams = {'currencytype': self.__strateg_config['currency_type'],
                 'subscribes': [{'type': marketcap.subscribetype.realprice, 'func': self.push_rt_price}]}
        capture.setparam(prams)

        # for test
        prams = {'subscribes': [{'type': marketcap.subscribetype.realprice, 'func': self.__trader.push_rt_price}]}
        capture.setparam(prams)
        pass

    def start_running(self):
        self.get_grid_status()
        #_thread.start_new_thread(self.oder_status_tracking)
        self.print_running_status()

        threading.Thread(target = self.oder_status_tracking).start()

        return

    def push_rt_price(self, priceinfo: Price):
        # print("%s-%s"%(time.time()*1000,priceinfo.timestamp))
        self.__fresh_price = priceinfo
        if time.time() - float(priceinfo.timestamp)/1000.0 < 3:
            self.sale_judge(priceinfo.buy)
            self.buy_judge(priceinfo.sell)
        return

    #未成交订单状态跟踪查询
    def oder_status_tracking(self):
        while (1):
            deleteorids = []
            for order_id in list(self.__tracking_orders.keys()):
                orderinfo = self.__trader.getorderlist(Ordertype(self.__tracking_orders[order_id]), 0, order_id, Currency(self.__strateg_config['currency_type']))
                # 更新内存中的订单状态比较、更新（并更新数据库）
                if orderinfo._totalcount != 0.0:
                    self.push_order_status(orderinfo)

                if orderinfo._totalcount == orderinfo._acceptcount and orderinfo._totalcount != 0:
                    # 订单成交,从订单跟踪列表中删除
                    deleteorids.append(order_id)

            for delorderid in deleteorids:
                self.__tracking_orders.pop(str(delorderid))
                print("pop traking order:%s"% str(delorderid))
            deleteorids.clear()
            time.sleep(1)

        return

    # order_id 交易ID
    # volume 成交量
    def push_order_status(self, orderinfo):
        order_id = orderinfo._id
        needUpdateDb = False
        ordertypename = None
        if orderinfo._type == Ordertype.Sale:
            ordertypename = 'onsale_order'
        elif orderinfo._type == Ordertype.Purchase:
            ordertypename = 'onpurchase_order'
        if ordertypename is None:
            return

        for griditem in self.__grid_running_status['grid_lines']:
            if str(order_id) not in griditem.get(ordertypename, {}):
                continue
            chang_order = griditem[ordertypename][str(order_id)]

            if chang_order['count'] != orderinfo._totalcount - orderinfo._acceptcount:
                accept_count = chang_order['count'] - (orderinfo._totalcount - orderinfo._acceptcount)

                # order_info {'time':2129918829 ,'strategy_id':ObjectId, 'trade_type':Ordertype.Sale.Value, 'vol':10.0, 'price':85.0, 'cost_price':84.0}
                trade_record = {'time': time.time(),
                                'strategy_id': self.__grid_running_status['strategy_id'],
                                'trade_type': orderinfo._type.value,
                                'vol': accept_count,
                                'price': chang_order['price'],
                                'cost_price': chang_order.get('cost_price', 0.0)}
                self.__trade_db.deal_order(trade_record)
                cost_price = chang_order['cost_price']
                deal_price = chang_order['price']
                if orderinfo._type == Ordertype.Purchase: #买单成交,下卖单并更新买单数据

                    new_order_id = self.__trader.makeoder(griditem['sale_price'],
                                                    Ordertype.Sale,
                                                    accept_count,
                                                    Currency(self.__strateg_config['currency_type']))

                    # TODO::Cost Price 在更新时若Order Id为0 需要重新计算平均成本价格

                    if str(new_order_id) in griditem.get('onsale_order', {}):
                        cost_price = ((chang_order['price'] * accept_count +
                                      griditem['onsale_order'].get(str(new_order_id), {}).get('count', 0) *
                                      griditem['onsale_order'].get(str(new_order_id), {}).get('cost_price', 0)) /
                                      (accept_count + griditem['onsale_order'].get(str(new_order_id), {}).get('count', 0)))

                    griditem.setdefault('onsale_order', {})[str(new_order_id)] = (
                                                                        {'count': accept_count + griditem['onsale_order'].get(str(new_order_id), {}).get('count', 0.0),
                                                                         'price': griditem['sale_price'], 'cost_price': cost_price})
                    if new_order_id != 0:
                        self.__tracking_orders.update({str(new_order_id): Ordertype.Sale.value})
                        print("add traking order:%s"% str(new_order_id))
                elif orderinfo._type == Ordertype.Sale: #卖单成交,更新配额
                    # accept_amount = (griditem[ordertypename][str(order_id)]['count'] - (orderinfo._totalcount - orderinfo._acceptcount))
                    griditem['quota'] += accept_count
                    griditem['break_even'] = griditem.get('break_even', 0.0) + (accept_count * (deal_price - cost_price))

                if 0 != orderinfo._totalcount - orderinfo._acceptcount:
                    chang_order['count'] = orderinfo._totalcount - orderinfo._acceptcount
                else:
                    griditem[ordertypename].pop(str(order_id))

                needUpdateDb = True
                break

        if needUpdateDb == True:
            self.__db_collection.update({'strategy_id': self.__strateg_config['_id']}, self.__grid_running_status)

        return

    '''
    def push_ma_price(self, maprices, captime):
        self.__maprices = maprices;
        self.__mapricesupdatetime = captime;
        return
    '''


    def get_grid_status(self):
        strategy_status = self.__db_collection.find({'strategy_id': self.__strateg_config['_id']})
        if strategy_status.count() < 1:
            # init strategy status
            self.__grid_running_status = {'strategy_id': self.__strateg_config['_id']}
            base_price = self.__strateg_config['config']['base_price']
            grid_cost = self.__strateg_config['config']['cost_input'] / self.__strateg_config['config']['grid_count']
            for i in range(1, self.__strateg_config['config']['grid_count']):
                grid_line = {}
                grid_line['grid_idx'] = i
                grid_line['purchase_price'] = round(base_price*((1-0.019)**(i-1)), 2)
                grid_line['sale_price'] = round(grid_line['purchase_price']*(0.015+1.001**i), 2)
                grid_line['count'] = round(grid_cost / grid_line['purchase_price'], 2)
                grid_line['quota'] = grid_line['count']
                if 'grid_lines' not in self.__grid_running_status:
                    self.__grid_running_status['grid_lines'] = []
                self.__grid_running_status['grid_lines'].append(grid_line)
            self.__db_collection.insert(self.__grid_running_status)
        else:
            self.__grid_running_status = strategy_status[0]
            for item in self.__grid_running_status['grid_lines']:
                self.__tracking_orders.update({k: Ordertype.Sale.value for k in item.get('onsale_order', {}).keys()})
                self.__tracking_orders.update({k: Ordertype.Purchase.value for k in item.get('onpurchase_order', {}).keys()})

                # just for test
                if type(self.__trader) is trade_test:
                    self.__trader.add_order(
                        item.get('onsale_order', {}))
                    self.__trader.add_order(
                        item.get('onpurchase_order', {}))
                # just for test

        return
    # Sell all TC
    # Cancel unsettled order
    # Remove strategy cin db
    def cancel_strategy(self):
        return
    def get_total_cny(self, totalcny):
        return


    def sale_judge(self, price):
        # 找到订单号为0的卖单（订单号为0表示，下单失败的订单）
        # ordertypes = ['onsale_order', 'onpurchase_order']
        need_update_db = False
        for griditem  in self.__grid_running_status['grid_lines']:
                if '0' in griditem.get('onsale_order', []):
                    order_id = self.__trader.makeoder(griditem['sale_price'],
                                           Ordertype.Sale,
                                           griditem['onsale_order']['0']['count'],
                                           Currency(self.__strateg_config['currency_type']))
                    if order_id != 0:
                        griditem['onsale_order'][str(order_id)] = griditem['onsale_order']['0']
                        griditem['onsale_order'].pop('0')
                        need_update_db = True
                        self.__tracking_orders.update({str(order_id): Ordertype.Sale.value})
                        print("add traking order:%s" % str(order_id))

        if need_update_db == True:
            self.__db_collection.update({'strategy_id': self.__strateg_config['_id']}, {'$set': {'grid_lines': self.__grid_running_status['grid_lines']}})
        return

    def buy_judge(self, price):
        #找到当前价格匹配的网格（多挡都匹配的话，只买最低一档）
        lowest_grid_price = 0.0
        lowest_idx = 0
        for idx, grid_item in enumerate(self.__grid_running_status['grid_lines']):
            if price <= grid_item['purchase_price'] and (grid_item['purchase_price'] < lowest_grid_price or lowest_grid_price == 0.0):
                if grid_item['quota'] > 0.0:
                    lowest_grid_price = grid_item['purchase_price']
                    lowest_idx = idx

        grid_item = self.__grid_running_status['grid_lines'][lowest_idx]
        if lowest_grid_price != 0:
            _orderid = self.__trader.makeoder(price, Ordertype.Purchase, grid_item['quota'], Currency(self.__strateg_config['currency_type']))
            if 0 != _orderid:
                grid_item.setdefault('onpurchase_order', {}).update({str(_orderid): {'count': grid_item['quota'], 'price': price, 'cost_price': price}})
                grid_item['quota'] = 0
                self.__tracking_orders.update({str(_orderid): Ordertype.Purchase.value})
                print("add traking order:%s" % str(_orderid))
                self.__db_collection.update({'strategy_id': self.__strateg_config['_id']},
                                            {'$set': {'grid_lines': self.__grid_running_status['grid_lines']}})
        return

    def get_breakeven(self, start_time = 0, stop_time = 0):
        fOnsaleBreakEven = 0.0
        if self.__fresh_price.last != 0.0:
            hold_ec = self.get_current_hold_bt()
            for cost_price, count in hold_ec.items():
                fOnsaleBreakEven += (self.__fresh_price.last*count - cost_price * count)

        fOnsaleBreakEven += self.__trade_db.get_breakeven(start_time, stop_time)

        return fOnsaleBreakEven

        # for griditem in self.__grid_running_status['grid_lines']:
        #     fOnsaleBreakEven += griditem.get('break_even', 0.0)
        #     if 'onsale_order' in griditem :
        #         fOnsaleCount = functools.reduce((lambda x, y: x+y.get('count', 0)), griditem.get('onsale_order', {}).values(), 0)
        #         if fOnsaleCount > 0.0 and self.__fresh_price.last != 0:
        #             fOnsaleBreakEven += ((self.__fresh_price.last - griditem['purchase_price']) * fOnsaleCount)
        # return fOnsaleBreakEven

    def print_running_status(self):

        ISFORMAT = "%Y-%m-%d %H:%M:%S"
        print('\n当前价格:%f 时间:%s-本地时间:%s' %
              (self.__fresh_price.last, time.strftime(ISFORMAT, time.localtime(self.__fresh_price.timestamp/1000),
                                                      ), time.strftime(ISFORMAT, time.localtime())))
        print("总盈亏:%f"%(self.get_breakeven()))
        print(self.__grid_running_status['grid_lines'])

        if (time.time() - self.__fresh_price.timestamp/1000) > 10 and self.__fresh_price.last != 0.0:
            print("##############实时价格长时间未更新##############")
        threading.Timer(15, self.print_running_status).start()
        pass

    def get_current_hold_bt(self):
        btmap = {}
        for grid in self.__grid_running_status['grid_lines']:
            # btlist.append({v['price']: v['count'] for k, v in grid.get('onsale_order', {}).items()})
            for k, v in grid.get('onsale_order', {}).items():
                if 'cost_price' in v:
                    btmap.update({v['cost_price']: v['count']+btmap.get(v['cost_price'], 0.0)})
        return btmap


