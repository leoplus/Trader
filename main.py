import http.client
import json

import sys
from pymongo import MongoClient

import marketcap
from market_recorder import market_recorder
from publicdef import StrategType, Currency, Ordertype, subscribetype, Strategy_Factory
from strategygrid import strategy_grid
from suona import sms
from trade_cnbtc import trade_cnbtc

# g_okcoinurl = r"api.chbtc.com"

def httpget(url,resource,params=''):
    conn = http.client.HTTPConnection(url, timeout=3)
    conn.request("GET", resource+"?"+params)
    response = conn.getresponse()
    rescode = response.getcode()
    if(rescode == 200):
        data = response.read().decode("utf-8")
        return json.loads(data)
    else:
        return ""

def deal_maprice(ma_price):
    print("[%d] MA unit:%d range:%d price:%f highest:%f lowest:%f vod:%f"%(ma_price.ticket,
                                                                           ma_price.unit,
                                                                           ma_price.period,
                                                                           ma_price.close_price,
                                                                           ma_price.highest,
                                                                           ma_price.lowest,
                                                                           ma_price.vol))

    pass

if __name__ == '__main__':
    trader = trade_cnbtc()
    # trader.getaccountasset()
    # orderid = trader.makeoder(1, Ordertype.Purchase, 0.5)
    # orderid = '2017031662132347'
    # order_info = trader.getorderlist(Ordertype.Sale, 0, orderid, Currency.eth)
    # trader.cancelorder(orderid)

    # trader.getaccountasset();
    #trader.getorderlist(0,2,2016063021633688)
    #trader.cancelorder(2016063021633688)
    #orderid = 0
    #orderid = trader.makeoder(1.2,2,0.5)
    #print(orderid)
    #
    notifyer = sms()
    notifyer.notify_make_order_with_assets(Ordertype.Purchase, 111.11111, 222.22222, 33333.3333)

    strategy = strategy_grid()

    # strategy.push_rt_price(0.0, 000);

    marketer = marketcap.Marketcap()

    # prams = {"currencytype":currency.eth}
    # {currencytype:currency.eth,subscribes:[{type:1,maunit:1,marange:5,func:fun},{}]}
    # prams = {'subscribes': [{'type': marketcap.subscribetype.realprice, 'func': strategy.push_rt_price}]}
    # marketer.setparam(prams)

    # marketer.caprealtimeprice()
    #marketer.caprealmaprice(1,5)
    dbClient = MongoClient('mongodb://localhost:27017')
    db = dbClient['tcTrader']
    collection = db['TraderConfig']
    strateg_cfg = {'strategy_type': StrategType.Grid.value, 'currency_type': Currency.eth.value, 'config': {'base_price': 87.2, 'grid_count': 10, 'grid_size': 0.01, 'cost_input': 5000.0}}
    #collection.insert_one(strateg_cfg)
    #rs = collection.find({'_id': ObjectId('58a40b2bc046b02cdc6ac9d6')})
    #collection.update({'_id': ObjectId('58a40b2bc046b02cdc6ac9d6')}, {'$set': strateg_cfg})
    #collection.remove({'_id': ObjectId("58a56b38c046b036b8c5bd69")})
    strategys = []
    if "caponly" not in sys.argv:
        specific_strategy_name = ""
        if "-s" in sys.argv:
            alias_idx = sys.argv.index('-s')
            if alias_idx+1 < len(sys.argv):
                specific_strategy_name = sys.argv[alias_idx+1]

        for item in collection.find({'strategy_type': {'$exists': True}}):
            if item.get('alias', "") != specific_strategy_name:
                continue
            strategy_instance = Strategy_Factory(StrategType(item['strategy_type']))
            strategy_instance.set_strateg_config(item)
            strategy_instance.set_market_capture(marketer)
            strategy_instance.start_running()
            strategys.append(strategy_instance)
            if specific_strategy_name:
                break

    if "cap" in sys.argv or "caponly" in sys.argv:
        recorder = market_recorder()
        recorder.set_marketcap(marketer)
        recorder.start_record()

    # param = {'subscribes': {'type': subscribetype.maprice,
    #                         'func': deal_maprice,
    #                         'params': {'maunit': 15, 'marange': 5}}}
    # marketer.setparam(param)
    # param = {'currencytype': 2}
    # marketer.setparam(param)
    # param = {'subscribes': {'type': subscribetype.maprice,
    #                         'func': deal_maprice,
    #                         'params': {'maunit': 15, 'marange': 10}}}
    # marketer.setparam(param)
    # param = {'subscribes': {'type': subscribetype.maprice,
    #                         'func': deal_maprice,
    #                         'params': {'maunit': 15, 'marange': 30}}}
    # marketer.setparam(param)

    marketer.start_capture()
