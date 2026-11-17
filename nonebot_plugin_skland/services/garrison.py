"""卫戍协议的账号级读取编排。"""

from ..model import SkUser
from ..schemas import CRED
from ..api import SklandAPI
from .auth import CredentialState, refresh_credentials
from ..schemas.arknights.garrison import GarrisonData, GarrisonResources


@refresh_credentials
async def fetch_garrison(
    user: SkUser | CredentialState,
    uid: str,
    *,
    activity_id: str | None = None,
) -> tuple[GarrisonData, GarrisonResources, str]:
    cred = CRED(cred=user.cred, token=user.cred_token)
    resources = await SklandAPI.ark_garrison_resources(cred, activity_id=activity_id)
    resolved_activity = activity_id or resources.current_activity_id
    data = await SklandAPI.ark_garrison(cred, uid=uid, activity_id=resolved_activity)
    return data, resources, resolved_activity
