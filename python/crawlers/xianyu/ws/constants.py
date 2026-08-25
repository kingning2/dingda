"""闲鱼 IM WebSocket 协议常量。"""

WS_URL = "wss://wss-goofish.dingtalk.com/"
WEB_ORIGIN = "https://www.goofish.com/"
LOGIN_TOKEN_URL = "https://h5api.m.goofish.com/h5/mtop.taobao.idlemessage.pc.login.token/1.0/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

HEARTBEAT_INTERVAL_SEC = 15
TOKEN_REFRESH_INTERVAL_SEC = 3600
VULCAN_WAIT_SEC = 8

HISTORY_PAGE_LIMIT = 50
HISTORY_MAX_PAGES = 3
HISTORY_RESPONSE_TIMEOUT_SEC = 10
HISTORY_FIRST_CURSOR = 9_007_199_254_740_991

APP_KEY = "34839810"
REG_APP_KEY = "444e9908a51d1cb236a27862abc769c9"
