from pymongo import MongoClient

from publicdef import Ordertype


class Trading:
    def __init__(self):
        dbClient = MongoClient('mongodb://localhost:27017')
        db = dbClient['tcTrader']
        self.__db_collection = db['DO']
        pass

    # order_info {'time':2129918829 ,'strategy_id':ObjectId, 'trade_type':Ordertype.Sale.Value, 'vol':10.0, 'price':85.0, 'cost_price':84.0}
    def deal_order(self, order_info):
        self.__db_collection.insert(order_info)

    def find_order(self, start_time, end_time):
        return list(self.__db_collection.find({'time': {'$lt': start_time, '$gt': end_time}}))

    def get_breakeven(self, start_time, end_time):
        find_condition = {'trade_type': Ordertype.Sale.value}
        if start_time != 0 and end_time != 0:
            find_condition.update({'time': {'$lt': start_time, '$gt': end_time}})

        breakeven_count = 0.0
        result = self.__db_collection.find(find_condition, {'vol': 1, 'cost_price': 1, 'price': 1})
        for item in result:
            breakeven_count += (item['price']*item['vol'] - item['cost_price']*item['vol'])

        return breakeven_count
