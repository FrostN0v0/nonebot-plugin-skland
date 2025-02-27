from pydantic import BaseModel


class Trainee(BaseModel):
    charId: str
    targetSkill: int
    ap: int
    lastApAddTime: int


class Trainer(BaseModel):
    charId: str
    ap: int
    lastApAddTime: int


class Training(BaseModel):
    slotId: str
    level: int
    trainee: Trainee
    trainer: Trainer
    remainPoint: float
    speed: float
    lastUpdateTime: int
    remainSecs: int
    slotState: int
