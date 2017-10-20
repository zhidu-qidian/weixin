# coding: utf-8

""" 微信公众号文章获取

利用 itchat 包，获取微信公众号推送的信息，从中获得公众号文章的永久链接

"""

import logging
import json
from urllib import quote

from logging.handlers import TimedRotatingFileHandler
base_format = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
filename = "log-weixin.log"
file_handler = TimedRotatingFileHandler(filename=filename, when='midnight', backupCount=15)
file_handler.setFormatter(base_format)
logging.getLogger().addHandler(file_handler)
logging.getLogger().setLevel(level=logging.INFO)

import itchat
from itchat.content import SHARING, TEXT
from pymongo import MongoClient
from redis import from_url

REDIS_URL = "redis://内网IP:6379"
# REDIS_URL = "redis://127.0.0.1:6379"
REDIS_MAX_CONNECTIONS = 10
REDIS_DB = 2

MONGODB_HOST_PORT = "内网IP:27017"
# MONGODB_HOST_PORT = "120.27.162.246:27017"
MONGODB_DATABASE = ""
MONGODB_USER = ""
MONGODB_PASSWORD = ""
COL_WEIXIN_MESSAGE = "weixin_message"


mp_mapping = dict()  # 公众号 user_name: nick_name 对照表
room_mapping = dict()  # 微信群 user_name: nick_name 对照表


def get_mongodb_database():
    url = "mongodb://{0}:{1}@{2}/{3}".format(MONGODB_USER,
                                             quote(MONGODB_PASSWORD),
                                             MONGODB_HOST_PORT,
                                             MONGODB_DATABASE)
    client = MongoClient(host=url, maxPoolSize=1, minPoolSize=1)
    return client.get_default_database()


db = get_mongodb_database()
redis = from_url(REDIS_URL, db=REDIS_DB, max_connections=REDIS_MAX_CONNECTIONS)


def show(data):
    for k, v in data.items():
        print k, ":", v
    print "*" * 120


@itchat.msg_register(TEXT, isGroupChat=True)
def get_group_message(msg):
    """ 在'微信爬虫测试群'里发 update, info 更新,获取相关信息 """
    user_name = msg["ToUserName"]
    nick_name = room_mapping.get(user_name)
    if nick_name == "jjyy":
        text = msg["Content"]
        if text == "update":
            update_mp_map()
            update_rooms_map()
            message = u"更新完成, %s个公众号, %s个群" % (len(mp_mapping), len(room_mapping))
            itchat.send(message, toUserName=user_name)
        elif text == "info":
            message = u"%s个公众号, %s个群" % (len(mp_mapping), len(room_mapping))
            itchat.send(message, toUserName=user_name)
        elif text == "dump":
            with open("mp.json", "w") as f:
                json.dump(mp_mapping, f)
            message = u"序列化公众号列表成功，请登录服务器查看"
            itchat.send(message, toUserName=user_name)


@itchat.msg_register(SHARING, isMpChat=True)
def get_mp_message(msg):
    """ 处理公众号推送的信息 """
    key = "weixin:message:id"
    user_name = msg["FromUserName"]
    if user_name not in mp_mapping:
        update_mp_map()
    nick_name = mp_mapping.get(user_name, "")
    if not nick_name:
        logging.error("not found user name %s" % user_name)
    else:
        logging.info("articles from %s" % nick_name)
        msg["__nick_name"] = nick_name
        _id = store(COL_WEIXIN_MESSAGE, msg)
        if _id:
            redis.lpush(key, _id)


def store(col_name, data):
    try:
        result = db[col_name].insert_one(data)
    except Exception:
        pass
    else:
        return str(result.inserted_id)
    return ""


def update_mp_map():
    mps = itchat.get_mps()
    for mp in mps:
        mp_mapping[mp["UserName"]] = mp["NickName"]


def update_rooms_map():
    rooms = itchat.get_chatrooms()
    for room in rooms:
        room_mapping[room["UserName"]] = room["NickName"]


def main():
    logging.info("login")
    itchat.auto_login(hotReload=True, enableCmdQR=2)
    update_rooms_map()
    update_mp_map()
    itchat.run()
    itchat.dump_login_status()


if __name__ == "__main__":
    main()
