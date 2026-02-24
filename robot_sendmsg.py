import base64
import hashlib
import hmac
from datetime import datetime

import requests

WEBHOOK_URL = "https://open.feishu.cn/open-apis/bot/v2/hook/18a2d270-e6b7-470c-b289-139c40b8f0ae"
WEBHOOK_SECRET = ""
timestamp = int(datetime.now().timestamp())


def gen_sign(secret):
    # 拼接时间戳以及签名校验
    string_to_sign = '{}\n{}'.format(timestamp, secret)

    # 使用 HMAC-SHA256 进行加密
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
    ).digest()

    # 对结果进行 base64 编码
    sign = base64.b64encode(hmac_code).decode('utf-8')

    return sign


def send_message(content):
    sign = gen_sign(WEBHOOK_SECRET)
    params = {
        "timestamp": timestamp,
        "sign": sign,
        "msg_type": "text",
        "content": f'{{"text":"{content}"}}'
    }

    resp = requests.post(WEBHOOK_URL, json=params)
    resp.raise_for_status()
    result = resp.json()
    if result.get("code") and result.get("code") != 0:
        print(f"发送失败：{result['msg']}")
        return
    print("消息发送成功")
