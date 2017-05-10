import time
from random import uniform
from datetime import datetime

from publicdef import Currency, OrderInfo, Ordertype, Price

def priceinfo():
    pass

class trade_test:
    __rand_count = 0
    __order_id = 0
    __order_list = {}
    __fresh_price = Price()

    def __init__(self):
        pass

    def makeoder(self, price, ordertype, amount, encurrency=Currency.eth):

        self.__rand_count += 1
        if (self.__rand_count % 3) == 0:
            return 0
        self.__order_id = int(time.time())
        self.__order_list.update({self.__order_id: {'amount': amount, 'accept': 0.0, 'price': price}})

        print("[%s] New order, id:%d ordertype(%s) price:%f ,amount:%f" % ('{0:%Y-%m-%d %H:%M:%S}'.format(datetime.now()),
                                                                     self.__order_id,
                                                                     ordertype.__str__(),
                                                                     price, amount))
        return self.__order_id

    def cancelorder(self, orderid, encurrency=Currency.eth):
        self.__rand_count += 1
        if (self.__rand_count % 3) == 0:
            return False

        self.__order_list.pop(orderid)
        return True

    def getorderlist(self, ordertype, orderstatus, orderid=0, encurrency=Currency.eth):

        Order_id  = int(orderid)
        if Order_id == 0 or self.__fresh_price.buy == 0.0:
            return OrderInfo(Order_id, ordertype, 0.0, 0.0)

        self.__rand_count += 1
        if (self.__rand_count % 3) != 0:
            if Order_id in self.__order_list:
                if (ordertype == Ordertype.Sale and self.__fresh_price.buy < self.__order_list[Order_id]['price']) or \
                    (ordertype == Ordertype.Purchase and self.__fresh_price.sell > self.__order_list[Order_id]['price']):
                    return OrderInfo(Order_id, ordertype, 0.0, 0.0)

                amount = self.__order_list[Order_id]['amount']
                if amount - self.__order_list[Order_id]['accept'] > 1.0:
                    newaccept = uniform(self.__order_list[Order_id]['accept'], amount)
                    self.__order_list[Order_id]['accept'] = newaccept

                    print("[%s] deal id:%s  ordertype(%s) accept:%f ,amount:%f" % ('{0:%Y-%m-%d %H:%M:%S}'.format(datetime.now()),
                                                                                   Order_id,
                                                                                   ordertype.__str__(),
                                                                                   self.__order_list[Order_id]['accept'],
                                                                                   amount))
                    return OrderInfo(Order_id, ordertype, amount,
                                     self.__order_list[Order_id]['accept'])
                else:
                    self.__order_list.pop(Order_id)
                    print("[%s] deal id:%s  ordertype(%s) accept:%f ,amount:%f" % ('{0:%Y-%m-%d %H:%M:%S}'.format(datetime.now()),
                                                                                   Order_id, ordertype.__str__(), amount, amount))
                    return OrderInfo(Order_id, ordertype, amount, amount)
        return OrderInfo(Order_id, ordertype, 0.0, 0.0)

    def add_order(self, orders):
        for k, v in orders.items():
            self.__order_list.update({k: {'amount': v['count'], 'accept': 0.0, 'price': v['price']}})
        # self.__order_id = int(max(self.__order_list.keys(), default=self.__order_id))

        return
    def getaccountasset(self, assettype=0, assetstatus=0):
        return

    def push_rt_price(self, priceinfo):
        self.__fresh_price = priceinfo
        return