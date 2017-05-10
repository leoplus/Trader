from enum import Enum

def Strategy_Factory(x):
    from strategy_ma import strategy_ma
    from strategygrid import strategy_grid

    return {
        StrategType.Grid: strategy_grid(),
        StrategType.MA: strategy_ma()
    }[x]

class Currency(Enum):
    none = 0
    rmb = 1
    eth = 2
    btc = 3
    ltc = 4
    pass

class  Price:
    def __init__(self, last: float = 0.0, sell: float = 0.0,
                 buy: float = 0.0, vol: float = 0.0, timestamp: float = 0.0,
                 high=0.0, low=0.0):
        self.last = last
        self.sell = sell
        self.buy = buy
        self.vol = vol
        self.high = high
        self.low = low
        self.timestamp = timestamp

    def __iter__(self):
        yield 'last', self.last
        yield 'sell', self.sell
        yield 'buy', self.buy
        yield 'vol', self.vol
        yield 'high', self.high
        yield 'low', self.low
        yield 'timestamp', self.timestamp
        pass

    def from_dict(self, dict):
        for k, v in dict.items():
            setattr(self, k, v)
        pass

    def print(self):
        print(self.buy)
        return
    pass

class MaPrice:
    unit = 0        # min
    period = 0
    highest = 0.0
    lowest = 0.0
    close_price = 0.0
    vol = 0.0
    ticket = 0
    fresh_price = 0.0

    def __init__(self, unit, period, highest, lowest, close_price, vod, ticket, fresh_price):
        self.unit = unit
        self.period = period
        self.highest = highest
        self.lowest = lowest
        self.close_price = close_price
        self.vol = vod
        self.ticket = ticket
        self.fresh_price = fresh_price
        pass
    pass

class subscribetype(Enum):
    realprice = 1
    maprice = 2
    macd = 3
    pass

class StrategType(Enum):
    Grid = 1
    MA = 2
    pass

class Ordertype(Enum):
    Sale = 1
    Purchase = 2
    def __str__(self):
        return {1: "卖",
                 2: "买"}.get(self.value, "未知")
    pass

class OrderInfo:
    _id = 0
    _type = 0
    _totalcount = 0
    _acceptcount = 0

    def __init__(self, id, type, totalcount, accept = 0.0):
        self._id = id
        self._type = type
        self._totalcount = totalcount
        self._acceptcount = accept
        pass