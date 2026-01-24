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
    trainee: Trainee | None = None
    trainer: Trainer | None = None
    remainPoint: float
    speed: float
    lastUpdateTime: int
    remainSecs: int
    slotState: int

    @property
    def training_state(self) -> str:
        if self.trainee:
            if self.trainee.targetSkill == -1:
                return "空闲中"
            else:
                match self.trainee.targetSkill:
                    case -1:
                        return "空闲中"
                    case 0:
                        return "1技能"
                    case 1:
                        return "2技能"
                    case 2:
                        return "3技能"
        return "空闲中"
