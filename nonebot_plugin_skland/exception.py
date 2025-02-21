from nonebot.exception import NoneBotException


class Exception(NoneBotException):
    """异常基类"""


class RequestException(Exception):
    """请求错误"""
