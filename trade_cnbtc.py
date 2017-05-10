from opt.chbtc_api_python import Chbtc_Api
from publicdef import Currency, OrderInfo, Ordertype
from user_setting import user_setting

g_protect_min_saleprice = 1
g_protect_max_buyprict = 100

def chbtctradetype_systemtradetype(x):
    return {0: Ordertype.Sale, 1: Ordertype.Purchase}[x]

def systemtradeType_chbtctradetype(x):
    return {Ordertype.Sale: 0, Ordertype.Purchase: 1}[x]


#import datetime

class trade_cnbtc:
    __access_key = None
    __secret_key = None
    __currencystr = {
        Currency.rmb: 'cny',
        Currency.eth: 'eth',
        Currency.btc: 'btc',
        Currency.ltc: 'ltc'}

    def __init__(self):
        configer = user_setting()
        self.__access_key = configer.get_config("trader", "chbtc_appkey")
        self.__secret_key = configer.get_config("trader", "chbtc_secretkey")
        return

    #ordertype 1:sales 2:buy

    @classmethod
    def makeoder(self,price, ordertype,amount, encurrency =Currency.eth):
        currencystr = self.__currencystr[encurrency]
        apires = 'order'
        if Ordertype.Sale == ordertype: #sell
            # ordertype = 0
            if price < g_protect_min_saleprice:
                return 0
        elif Ordertype.Purchase == ordertype: #buy
            pass
            # ordertype = 1
            # if price > g_protect_max_buyprict:
            #     return 0
        #chbtc交易类型1/0[buy/sell]
        params = 'method=order&accesskey=%s&price=%.2f&amount=%f&tradeType=%d&currency=%s' % (self.__access_key, price,
                                                                                              amount, systemtradeType_chbtctradetype(ordertype), currencystr)
        apihelper = Chbtc_Api(self.__access_key, self.__secret_key)
        response = apihelper.api_call(apires, params)
        if response is None or response.get('code') != 1000:
            print(response)
            return 0
        return response.get('id', 0)

    @classmethod
    def cancelorder(self, orderid, encurrency=Currency.eth):
        currencystr = self.__currencystr[encurrency]
        apires = 'cancelOrder'
        params = 'method=cancelOrder&accesskey=%s&id=%s&currency=%s' % (self.__access_key, orderid, currencystr)
        apihelper = Chbtc_Api(self.__access_key, self.__secret_key)
        response = apihelper.api_call(apires, params)

        if not response or response.get('code', 0) != 1000:
            print("cancel order:" + str(response))
            return False

        return True

    #ordertype  ,0:all 1:sales 2:buy
    #orderstatus,0:all 1:settled 2:unsettled
    @classmethod
    def getorderlist(self, ordertype, orderstatus, oderid=0, encurrency=Currency.eth):
        currencystr = self.__currencystr[encurrency]
        #curtimetick = datetime.datetime.now().microsecond/1000

        if 0 != oderid:
            apires = 'getOrder'
            params = 'method=getOrder&accesskey=%s&id=%s&currency=%s'%(self.__access_key, oderid, currencystr)
            apihelper = Chbtc_Api(self.__access_key, self.__secret_key)
            response = apihelper.api_call(apires, params)

            if response is None:
                return OrderInfo(0, 0, 0)
            print("Getorderlist:" + str(response))
            return OrderInfo(response.get('id', ''), chbtctradetype_systemtradetype(response.get('type', 0))
                             , response.get('total_amount', 0), response.get('trade_amount', 0))
        else:
            if 0 == ordertype:
                if 2 == orderstatus:
                    apires = 'getUnfinishedOrdersIgnoreTradeType'
                    params = 'method=getUnfinishedOrdersIgnoreTradeType&accesskey=%s&currency=%s&pageIndex=1&pageSize=20'%(self.__access_key,currencystr)
                    apihelper = Chbtc_Api(self.__access_key, self.__secret_key)
                    response = apihelper.api_call(apires, params)
                    print("Getorderlist:" + response)
        return




    #assettype      0:all,currency Enum
    #assetstatus    0:all,1:balance,2:frozen
    #reutrn {'cny': {'total': 8872.405, 'available': 8872.405, 'frozen': 0.0},
    #        'eth': {'total': 4.0154834, 'available': 4.0154834, 'frozen': 0.0}}
    @classmethod
    def getaccountasset(self,assettype = 0,assetstatus = 0):
        apires = 'getAccountInfo'
        params = 'method=getAccountInfo&accesskey='+self.__access_key
        apihelper = Chbtc_Api(self.__access_key, self.__secret_key)
        respons = apihelper.api_call(apires,params)
        respons = respons['result']
        print(str(respons))

        accountinfo = dict()
        #accountinfo['total'] =

        def _makeaccountinfo(responsedict, accountdict, parse_key, account_key=None):
            available = float(responsedict['balance'][parse_key]['amount']);
            frozen = float(responsedict['frozen'][parse_key]['amount']);
            accountinfo[account_key if account_key is not None else parse_key] = {
                'total': available + frozen,
                'available': available,
                'frozen': frozen
            }

        for k, v in self.__currencystr.items():
            _makeaccountinfo(respons, accountinfo, str(v).upper(), v)

        '''
        rmbavailable = float(respons['balance']['CNY']['amount']);
        rmbfrozen    = float(respons['frozen']['CNY']['amount']);
        accountinfo['rmb'] = {'total':rmbavailable+rmbfrozen,
                             'available':rmbavailable,
                              'frozen':rmbfrozen}

        ethavailable = float(respons['balance']['ETH']['amount']);
        ethfrozen    = float(respons['frozen']['ETH']['amount']);
        accountinfo['eth'] = {'total':ethavailable+ethfrozen,
                              'available':ethavailable,
                              'frozen':ethfrozen}
        '''

        return accountinfo

    def add_order(self, orders):
        return True

