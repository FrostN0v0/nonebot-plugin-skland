from pydantic import BaseModel


class AwardId(BaseModel):
    id: str
    type: int


class AwardInfo(BaseModel):
    id: str
    name: str
    count: int
    icon: str


class EndfieldSignResponse(BaseModel):
    ts: str
    awardIds: list[AwardId]
    resourceInfoMap: dict[str, AwardInfo]
    tomorrowAwardIds: list[AwardId]

    @property
    def award_summary(self) -> str:
        summary = []
        for award_id in self.awardIds:
            resource_info = self.resourceInfoMap.get(
                award_id.id, AwardInfo(id=award_id.id, name="未知物品", count=0, icon="")
            )
            name = resource_info.name
            count = resource_info.count
            summary.append(f"{name} x{count}")
        return "\n".join(summary)
