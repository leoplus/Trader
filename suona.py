from sys import argv

from opt.alidayu import AlibabaAliqinFcSmsNumSendRequest
from user_setting import user_setting


class sms:
    # __req = None
    __appkey = None
    __secret = None

    def __init__(self):
        # self.__req = AlibabaAliqinFcSmsNumSendRequest(self.__appkey, self.__secret)
        # self.__req = top.api.AlibabaAliqinFcSmsNumSendRequest()
        # self.__req.set_app_info(top.appinfo(self.__appkey, self.__secret))
        configer = user_setting()
        self.__appkey = configer.get_config("sms", "appkey")
        self.__secret = configer.get_config("sms", "appsecret")
        pass

    def notify(self, msg):
        # req.extend = "123456"
        req = AlibabaAliqinFcSmsNumSendRequest(self.__appkey, self.__secret)
        req.sms_type = "normal"
        req.sms_free_sign_name = "TC消息"
        req.sms_param = "{\"content\":\"%s\"}" %(msg)
        req.rec_num = "15982802424"
        req.sms_template_code = "SMS_49135025"
        return self.sendmsg(req)

    def notify_make_order(self, optype, price, amount):
        # return True
        req = AlibabaAliqinFcSmsNumSendRequest(self.__appkey, self.__secret)
        req.sms_type = "normal"
        req.sms_free_sign_name = "TC消息"
        req.rec_num = "15982802424"
        req.sms_template_code = "SMS_57025052"
        req.sms_param = "{\"optype\":\"%s\", \"price\":\"%.2f\", \"amount\":\"%.2f\"}" % (str(optype), price, amount)
        return self.sendmsg(req)

    def notify_make_order_with_assets(self, optype, price, amount, assets):
        req = AlibabaAliqinFcSmsNumSendRequest(self.__appkey, self.__secret)
        req.sms_type = "normal"
        req.sms_free_sign_name = "TC消息"
        req.rec_num = "15982802424"
        req.sms_template_code = "SMS_57840090"
        req.sms_param = "{\"optype\":\"%s\", \"price\":\"%.2f\", \"amount\":\"%.2f\", \"balance\":\"%d\"}" % \
                        (str(optype), price, amount, assets)
        return self.sendmsg(req)

    def sendmsg(self, req):

        if 'debug' in argv or 'nosms' in argv:
            return True

        try:
            resp = req.getResponse()
            print(str(resp) + req.sms_param)
        except Exception as e:
            print(e)
            return False
        return True
