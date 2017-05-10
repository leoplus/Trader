import json, hashlib, struct, time, sys
import http.client
import ssl


class Chbtc_Api:
    def __init__(self, mykey, mysecret):
        self.__mykey    = mykey
        self.__mysecret = mysecret
        self.__apiurl = r"trade.chbtc.com"

    def __fill(self, value, lenght, fillByte):
        if len(value) >= lenght:
            return value
        else:
            fillSize = lenght - len(value)
        return value + chr(fillByte) * fillSize

    def __doXOr(self, s, value):
        slist = list(s)
        for index in range(len(slist)):
            slist[index] = chr(slist[index] ^ value)
        return "".join(slist)

    def __hmacSign(self, aValue, aKey):
        keyb   = struct.pack("%ds" % len(aKey), bytes(aKey,encoding='utf-8'))
        value  = struct.pack("%ds" % len(aValue), bytes(aValue,encoding='utf-8'))
        k_ipad = self.__doXOr(keyb, 0x36)
        k_opad = self.__doXOr(keyb, 0x5c)
        k_ipad = self.__fill(k_ipad, 64, 54)
        k_opad = self.__fill(k_opad, 64, 92)
        m = hashlib.md5()
        #k_ipad.encode('utf-8')
        m.update(k_ipad.encode('utf-8'))
        m.update(value)
        dg = m.digest()
        
        m = hashlib.md5()
        m.update(k_opad.encode('utf-8'))
        subStr = dg[0:16]
        m.update(subStr)
        dg = m.hexdigest()
        return dg

    def __digest(self, aValue):
        value  = struct.pack("%ds"%(len(aValue)), bytes(aValue,encoding='utf-8'))
        print(value)
        dg = hashlib.sha1(value).hexdigest();
        #h.update(value)
        #dg = h.hexdigest()
        return dg

    def api_call(self, path, params=''):
        try:
            SHA_secret = self.__digest(self.__mysecret)
            sign = self.__hmacSign(params, SHA_secret)
            reqTime = (int)(time.time()*1000)
            params += '&sign=%s&reqTime=%d'%(sign, reqTime)
            conn = http.client.HTTPSConnection(self.__apiurl, timeout=2, context=ssl._create_unverified_context())
            reqres = "/api/%s?%s"%(path, params)
            conn.request("GET", reqres)
            response = conn.getresponse()
            reponsecode = response.getcode()
            if(200 == reponsecode):
            ##url = 'https://trade.chbtc.com/api/' + path + '?' + params
            ##request = urllib2.Request(url)
            ##response = urllib2.urlopen(request, timeout=2)
                doc = json.loads(response.read().decode('utf-8'))

                return doc
            else:
                print("func[%s](%s) resultcode:%d\n"%(sys._getframe().f_code.co_name,params,reponsecode))

            return
        except Exception as ex:
            print('chbtc request ex: %s'%(ex),file=sys.stderr)
            return None

    def query_account(self):
        try:
            params = "method=getAccountInfo&accesskey="+self.mykey
            path = 'getAccountInfo'
            
            obj = self.__api_call(path, params)
            #print obj
            return obj
        except Exception as ex:
            print('chbtc query_account exception,%s'%(ex),file=sys.stderr)
            return None

        

