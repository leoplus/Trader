import datetime
import queue
import threading
import time
from threading import Thread
import queue

from pymongo import MongoClient

import marketcap

from publicdef import Currency, Price

# DB Document
# {"_id" : ObjectId("58ec4ba90d1440aa1c3d69ea"),
#  "time_on_hour" : 1491879600,
#  "data" : [ { "timestamp" : 1491880874, "close" : 266.85, "sell" : 266.99, "buy" : 266.8, "vol" : 46444.271 }]
#  }

class market_recorder:
    __market_cap = None
    __rt_price_queue = queue.Queue()
    __is_working = None
    __write_threading = None
    __db_collection_chbtc_hd = None

    def __init__(self):
        dbClient = MongoClient("mongodb://127.0.0.1:27017")
        db = dbClient['tcTrader']
        self.__db_collection_chbtc_hd = db['HD_CHBTC']

        return

    def set_marketcap(self, market_cap):
        self.__market_cap = market_cap
        return

    def start_record(self):
        self.__is_working = True

        prams = {'currencytype': Currency.eth.value,
                 'subscribes': {'type': marketcap.subscribetype.realprice, 'func': self.push_rt_price}}
        self.__market_cap.setparam(prams)

        self.__write_threading = Thread(target=self.write_2_db_proc)
        self.__write_threading.start()
        self.clean_invalid_data()

        return

    def stop_record(self):
        self.__is_working = False
        if self.__write_threading:
            self.__write_threading.join()
        return

    def push_rt_price(self, priceinfo: Price):
        return self.__rt_price_queue.put(priceinfo)

    # 删除过期数据
    def clean_invalid_data(self):
        invalid_ticket = time.mktime((datetime.date.today() - datetime.timedelta(days=30)).timetuple())
        result = self.__db_collection_chbtc_hd.delete_many({'time_on_hour': {'$lt': invalid_ticket}})

        threading.Timer(3600, self.clean_invalid_data).start()
        return

    def write_2_db_proc(self):
        last_data_ticket = 0
        while self.__is_working:
            price_info = self.__rt_price_queue.get()
            if not price_info:
                continue

            ticket = int(price_info.timestamp//1000)
            ticket_on_hour = ticket - (ticket % 3600)
            if ticket - last_data_ticket >= 60 and last_data_ticket:
                print("data lost time({}s)".format(str(ticket - last_data_ticket)))
            if last_data_ticket != ticket:
                self.__db_collection_chbtc_hd.update({'time_on_hour': ticket_on_hour},
                                                     {'$push': {'data': {'timestamp': ticket,
                                                                         'close': price_info.last,
                                                                         'sell': price_info.sell,
                                                                         'buy': price_info.buy,
                                                                         'vol': price_info.vol}}},
                                                     upsert=True)
            else:
                result = self.__db_collection_chbtc_hd.update({'time_on_hour': ticket_on_hour, 'data.timestamp': ticket},
                                                     {'$set': {'data.$': {'timestamp': ticket,
                                                                          'close': price_info.last,
                                                                          'sell': price_info.sell,
                                                                          'buy': price_info.buy,
                                                                          'vol': price_info.vol}}})

            last_data_ticket = ticket
            self.__rt_price_queue.task_done()
        return
