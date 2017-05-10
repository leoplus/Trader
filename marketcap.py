import http.client
import json
import sys
import time
from itertools import groupby
from threading import Thread
import numpy
import talib
from pymongo import MongoClient

from publicdef import subscribetype, Currency, Price, MaPrice


class Marketcap:
    __apiurl = r"api.chbtc.com"
    __caprun = 0
    __maunits = {1: '1min', 3: '3min', 5: '5min', 15: '15min', 30: '30min',
               60*24: '1day', 60*24*3: '3day',
               60*24*7: '1week',
               60: '1hour', 60*2: '2hour', 60*4: '4hour', 60*6: '6hour', 60*12: '12hour'}
    __tcaprtprice = None
    __tcapmaprice = None

    __kline_currency = {
        Currency.eth: 'eth_cny',
        Currency.btc: 'btc_cny',
        Currency.ltc: 'ltc_cny'
    }
    __cap_currencytype = Currency.none
    __fresh_price = Price
    __real_price_cb = []

    __ma_subscribes_info = []  # {maunit:1, marange:15, func:fun}
    __macd_subscrebes_info = {} #{'unit':[func, func]}

    __fresh_ma_1min_kline = []
    __last_ma_1min_data_ticket = 0

    __fresh_ma_15min_kline = []
    __last_ma_15min_data_ticket = 0

    __ma_1min_kline_basedb = []
    __ma_15min_kline_basedb = []

    # [{
    #         'timestamp': rtprice.timestamp//1000,
    #         'close': rtprice.last,
    #         'buy': rtprice.buy,
    #         'sell': rtprice.sell,
    #         'vol': rtprice.vol
    #   }]
    __ma_rowdata_kline_basedb = []

    __max_min_kline = None

    @classmethod
    #{currencytype:currency.eth,subscribes:[{type:1, func:fun,params:{maunit:1, marange:15}},{}]}
    # MACD subscribes call back data {ticket:00000, dif:-0.11, dea:-0.22, bar:0.22}
    def setparam(self,parms):
        for k, v in parms.items():
            if k == 'currencytype':
                self.__cap_currencytype = Currency(v)
            if k == 'subscribes':
                # for subscribe in v:
                if v['type'] == subscribetype.realprice:
                    self.__real_price_cb.append(v['func'])
                if v['type'] == subscribetype.maprice:
                    ma_subscribe_info = v['params']
                    ma_subscribe_info.update({'func': v['func']})
                    self.__ma_subscribes_info.append(ma_subscribe_info)
                if v['type'] == subscribetype.macd:
                    self.__macd_subscrebes_info.setdefault(v['params']['unit'], []).append(v['func'])
        return

    def start_capture(self):
        self.__caprun = 1
        # if len(self.__real_price_cb) > 0:
        self.startcaprtprice()
        if len(self.__ma_subscribes_info) > 0:
            self.startcapmaprice()
        return

    def stop_capture(self):
        self.__caprun = 0
        self.stopcapmaprice()
        self.stopcaprtprice()
        return

    @classmethod
    def startcaprtprice(self):
        if(1 != self.__caprun):
            self.__tcaprtprice = Thread(target=self.caprealtimeprice)
            self.__tcaprtprice.start()
        return

    @classmethod
    def stopcaprtprice(self):
        if(None != self.__tcaprtprice):

            self.__tcaprtprice.join()
            self.__tcaprtprice = None
        return

    @classmethod
    def caprealtimeprice(self):
        apires = r"/data/v1/ticker"
        conn = http.client.HTTPConnection(self.__apiurl, timeout=3)
        while(1):
            currencytype = self.__kline_currency.get(self.__cap_currencytype)
            reqres = "%s?currency=%s" % (apires, currencytype)
            response = None
            try:
                conn.request("GET", reqres, headers={"Connection": " keep-alive"})
                response = conn.getresponse()
            except :
                conn.close()
                conn = http.client.HTTPConnection(self.__apiurl, timeout=3)
                continue

            if(200 == response.getcode()):
                rtpricejson = json.loads(response.read().decode('utf-8'))
                self.__fresh_price = Price(float(rtpricejson['ticker']['last']), float(rtpricejson['ticker']['sell']),
                                           float(rtpricejson['ticker']['buy']), float(rtpricejson['ticker']['vol']),
                                           float(rtpricejson['date']),
                                           float(rtpricejson['ticker']['high']), float(rtpricejson['ticker']['low']))
                # print("last:%s sell:%s buy:%s time:%s"% (
                #     self.__fresh_price.last, self.__fresh_price.sell, self.__fresh_price.buy, self.__fresh_price.timestamp))
                for callback_func in self.__real_price_cb:
                    callback_func(self.__fresh_price)

                self.udpate_madata_by_rtprice(self.__fresh_price)
                # self.udpate_maprice_by_rtprice(self.__fresh_price)
                time.sleep(0.4)

            elif  response.closed == True:
                conn.close()
                conn = http.client.HTTPConnection(self.__apiurl, timeout=3)
        return



    @classmethod
    def startcapmaprice(self):

        #judge is running

        self.__max_min_kline = max(item['maunit'] * item['marange'] for item in self.__ma_subscribes_info)
        self.get_ma_data_fromdb(1, self.__max_min_kline)

        # self.__tcapmaprice = Thread(target=self.caprealmaprice)
        # self.__tcapmaprice.start()

        return

    @classmethod
    def stopcapmaprice(self,unirange):
        if self.__tcapmaprice is not None:
            self.__tcapmaprice.join()
            self.__tcaprtprice = None
        return

    #unit,mins
    @classmethod
    def caprealmaprice(self):
        apires = r'/data/v1/kline'
        apiparam_type = self.__maunits.get(1)  # 全部数据以1分钟线为基础
        currencytype  = self.__kline_currency.get(self.__cap_currencytype)

        if(apiparam_type is None):
            print("%s pass parm manuit(%d) is not correct!\n"%(sys._getframe().f_code.co_name, self.__maunits.values()))
            return
        conn = http.client.HTTPConnection(self.__apiurl, timeout=10)
        maxmin = max(item['maunit'] * item['marange'] for item in self.__ma_subscribes_info)

        reqres = {}
        reqres[apiparam_type] = "%s?currency=%s&type=%s&size=%d" % (apires, currencytype, apiparam_type, maxmin)
        reqres[self.__maunits.get(15)] = "%s?currency=%s&type=%s&size=%d" % (apires,
                                                                             currencytype,
                                                                             self.__maunits.get(15),
                                                                             int(maxmin / 10))
        while True:
            for min_type, res in reqres.items():
                try:
                    conn.request("GET", res)
                    reponse = conn.getresponse()
                    if 200 != reponse.getcode():
                        continue
                    response_data = json.loads(reponse.read().decode('utf-8'))
                except Exception as ex:
                    print('func[%s],%s' % (sys._getframe().f_code.co_name, ex), file=sys.stderr)
                    conn.close()
                    time.sleep(3)
                    conn = http.client.HTTPConnection(self.__apiurl, timeout=3)
                    continue

                if 'data' in response_data:
                    fresh_data_ticket = max(dataitem[0] for dataitem in response_data['data'])
                    if min_type == self.__maunits.get(1):
                        if fresh_data_ticket > self.__last_ma_1min_data_ticket:
                            self.__fresh_ma_1min_kline = response_data['data']
                            self.__last_ma_1min_data_ticket = fresh_data_ticket
                    elif min_type == self.__maunits.get(15):
                        if fresh_data_ticket > self.__last_ma_15min_data_ticket:
                            self.__fresh_ma_15min_kline = response_data['data']
                            self.__last_ma_15min_data_ticket = fresh_data_ticket

                # totalprice = float(0)
                # rangehighprice  = maprices['data'][0-marange:][0][4]
                # rangelowprice   = rangehighprice
                # for maprice in maprices['data'][0-marange:]:
                #     totalprice += float(maprice[4])
                #     if maprice[4] > rangehighprice:
                #         rangehighprice = maprice[4]
                #     elif maprice[4] < rangelowprice:
                #         rangelowprice = maprice[4]
                #
                # curmaprice = totalprice / marange
                # print("%d average on %s,Price:%.2f High:%.2f low:%.2f\n"%(marange, apiparam_type, curmaprice, rangehighprice, rangelowprice))
            time.sleep(20)
        return

    @classmethod
    def udpate_maprice_by_rtprice(self, rtprice):
        if self.__fresh_ma_1min_kline:
            newprice = [rtprice.timestamp, rtprice.last, rtprice.last, rtprice.last, rtprice.last, 0]
            fresh_ma_data_ticekt = max(item[0] for item in self.__fresh_ma_1min_kline)
            if time.time() - fresh_ma_data_ticekt/1000 > 5*60:
                print("ma data over %d sec,no update" % (time.time() - fresh_ma_data_ticekt/1000))

            for subscribe in self.__ma_subscribes_info:
                rangeon1min = subscribe['maunit'] * subscribe['marange']
                filter_ticket = fresh_ma_data_ticekt - rangeon1min*60*1000
                tmplist = list(filter(lambda x: x[0] > filter_ticket, self.__fresh_ma_1min_kline))

                tmplist.insert(0, newprice)
                rangeon1min = len(tmplist)
                # avg = float(sum(kitem[4] for kitem in tmplist)) / rangeon1min
                # avg = numpy.average(list(kitem[4] for kitem in tmplist), weights=list(kitem[5] for kitem in tmplist))
                alpha = 2.0 / (rangeon1min + 1)
                avg = numpy.average(list(kitem[4] for kitem in tmplist), weights=list((1 - alpha) ** idx for idx, _ in enumerate(tmplist)))
                # avg2 = float(sum(kitem[4]*((1 - alpha) ** idx) for idx, kitem in enumerate(tmplist)))/\
                #           sum((1 - alpha)**i for i in range(0, rangeon1min-1))

                # avg3 = float(sum(kitem[4]*(1+idx) for idx, kitem in enumerate(tmplist)))/sum(range(1, rangeon1min))
                highest = max(kitem[2] for kitem in tmplist)
                lowest = min(kitem[3] for kitem in tmplist)
                vod = sum(kitem[5] for kitem in tmplist[int(0-subscribe['maunit']):])
                subscribe['func'](MaPrice(subscribe['maunit'], subscribe['marange'], highest, lowest, avg, vod, self.__last_ma_1min_data_ticket, rtprice))

        # Calc MACD
        for k, v in self.__macd_subscrebes_info.items():
            if k == 15 and self.__fresh_ma_15min_kline:
                kls = list(item[4] for item in self.__fresh_ma_15min_kline)
                kls.insert(0, rtprice.last)
                nplist = numpy.array(kls)
                macd, signal, hist = talib.MACD(nplist, fastperiod=12, slowperiod=26, signalperiod=9)
                # now_sma30 = talib.SMA(numpy.array(kls), timeperiod=30)

                macd_data = {'ticket': rtprice.timestamp,
                             'dif': macd[-1],
                             'dea': signal[-1],
                             'bar': hist[-1],
                             'fresh_price': dict(rtprice)}

                for func in v:
                    func(macd_data)

                # print("[{%s}] dif:{%f}, dea:{%f} bar:{%f}" % ('{0:%Y-%m-%d %H:%M:%S}'.format(datetime.now()),
                #                                               macd[-1],
                #                                               signal[-1],
                #                                               hist[-1]))

        return

    @classmethod
    def get_ma_data_fromdb(self, unit, range):
        client = MongoClient("mongodb://127.0.0.1:27017")
        db = client['tcTrader']
        collection = db['HD_CHBTC']
        time_ticket = time.time() - unit * range * 60 * 1.3
        condition = {"$match": {'data.timestamp': {'$gte': time_ticket}}}
        # k_data1 = list(collection.find({'data.timestamp': {'$gte': time_ticket}}))
        group = {'$group': {'_id': None, 'data': {'$push': '$data'}}}
        k_data = list(collection.aggregate([condition, {'$unwind': '$data'}, group]))

        if k_data:
            k_data = k_data[0].get('data', [])

        # datas = []
        if not k_data or len(k_data) <= unit * range * 50:
            k_data = list(self.request_kline_from_api(unit, range))

        self.__ma_rowdata_kline_basedb = sorted(k_data, key=lambda x: x['timestamp'])
        self.update_kline_data()

        return

    @classmethod
    def udpate_madata_by_rtprice(self, rtprice):
        if not self.__ma_rowdata_kline_basedb:
            return

        self.__ma_rowdata_kline_basedb.append({
            'timestamp': rtprice.timestamp//1000,
            'close': rtprice.last,
            'buy': rtprice.buy,
            'sell': rtprice.sell,
            'vol': rtprice.vol
        })

        time_ticket = rtprice.timestamp//1000 - self.__max_min_kline * 60 * 1.3
        self.__ma_rowdata_kline_basedb = list(filter(lambda x: x['timestamp'] >= time_ticket, self.__ma_rowdata_kline_basedb))

        self.update_kline_data()

        for subscribe in self.__ma_subscribes_info:
            rangeon1min = subscribe['maunit'] * subscribe['marange']
            filter_ticket = self.__ma_1min_kline_basedb[-1]['timestamp'] - rangeon1min * 60

            tmplist = list(filter(lambda x: x['timestamp'] > filter_ticket, self.__ma_1min_kline_basedb))
            alpha = 2.0 / (len(tmplist) + 1)
            avg = numpy.average(list(kitem['close'] for kitem in tmplist[::-1]),
                                weights=list((1 - alpha) ** idx for idx, _ in enumerate(tmplist)))
            highest = max(kitem['close'] for kitem in tmplist)
            lowest = min(kitem['close'] for kitem in tmplist)
            vod = sum(kitem['vol'] for kitem in tmplist[int(0 - subscribe['maunit']):])
            subscribe['func'](MaPrice(subscribe['maunit'], subscribe['marange'], highest, lowest, avg, vod,
                                      self.__last_ma_1min_data_ticket, rtprice))


        # Calc MACD
        for k, v in self.__macd_subscrebes_info.items():
            if k == 15 and self.__ma_15min_kline_basedb:
                kls = list(float(item['close']) for item in self.__ma_15min_kline_basedb)
                nplist = numpy.array(kls)
                macd, signal, hist = talib.MACD(nplist, fastperiod=12, slowperiod=26, signalperiod=9)
                macd_data = {'ticket': rtprice.timestamp,
                             'dif': macd[-1],
                             'dea': signal[-1],
                             'bar': hist[-1],
                             'fresh_price': dict(rtprice)}

                for func in v:
                    func(macd_data)
        return

    @classmethod
    def update_kline_data(self):
        self.__ma_1min_kline_basedb.clear()
        for key, group in groupby(self.__ma_rowdata_kline_basedb, key=lambda x: x['timestamp'] // 60):
            data_group = list(group)
            self.__ma_1min_kline_basedb.append({'timestamp': max(data_group, key=lambda x: x['timestamp'])['timestamp'],
                                         'close': data_group[-1]['close'],
                                         'sell': data_group[-1]['sell'],
                                         'buy': data_group[-1]['buy'],
                                         'vol': data_group[-1]['vol'] - data_group[0]['vol']})

        self.__ma_15min_kline_basedb.clear()
        for key, group in groupby(self.__ma_rowdata_kline_basedb, key=lambda x: x['timestamp'] // (60 * 15)):
            data_group = list(group)
            self.__ma_15min_kline_basedb.append({'timestamp': max(data_group, key=lambda x: x['timestamp'])['timestamp'],
                                          'close': data_group[-1]['close'],
                                          'sell': data_group[-1]['sell'],
                                          'buy': data_group[-1]['buy'],
                                          'vol': data_group[-1]['vol'] - data_group[0]['vol']})
        return

    @classmethod
    def request_kline_from_api(self, unit, range):
        apires = r'/data/v1/kline'
        apiparam_type = self.__maunits.get(1)  # 全部数据以1分钟线为基础
        currencytype = self.__kline_currency.get(self.__cap_currencytype)

        if (apiparam_type is None):
            print(
                "%s pass parm manuit(%d) is not correct!\n" % (sys._getframe().f_code.co_name, self.__maunits.values()))
            return
        conn = http.client.HTTPConnection(self.__apiurl, timeout=10)
        maxmin = max(item['maunit'] * item['marange'] for item in self.__ma_subscribes_info)
        res = "%s?currency=%s&type=%s&size=%d" % (apires, currencytype, apiparam_type, int(maxmin * 1.3))

        while True:
            try:
                conn.request("GET", res)
                reponse = conn.getresponse()
                if 200 != reponse.getcode():
                    continue
                response_data = json.loads(reponse.read().decode('utf-8'))
            except Exception as ex:
                print('func[%s],%s' % (sys._getframe().f_code.co_name, ex), file=sys.stderr)
                conn.close()
                time.sleep(3)
                conn = http.client.HTTPConnection(self.__apiurl, timeout=3)
                continue

            conn.close()
            break

        if 'data' in response_data:
            for item in response_data['data']:
                yield {
                        'timestamp': item[0]//1000,
                        'close': item[4],
                        'buy': item[4],
                        'sell': item[4],
                        'vol': item[5]
                }
        return