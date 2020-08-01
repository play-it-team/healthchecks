from enum import Enum


class ChoiceEnum(Enum):
    @classmethod
    def choices(cls):
        return tuple((i.name, i.value) for i in cls)


class CheckKind(ChoiceEnum):
    simple = "Simple"
    cron = "Cron"


class ChannelKind(ChoiceEnum):
    call = "Phone Call"
    email = "Email"
    sms = "SMS"


class Status(ChoiceEnum):
    up = "Up"
    down = "Down"
    paused = "Paused"
    new = "New"
