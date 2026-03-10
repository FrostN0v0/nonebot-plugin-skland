import httpx

from ..exception import RequestException

V4_URL = "https://fp-it.portal101.cn/deviceprofile/v4"
V4_DATA = (
    "4ac13cbe759d757cf4fd5465233024db2b7ae6bfbddd6d2d3eb964b246b2d4c3a8405b1601c3f3cc556257bd2784bfa6"
    "c1021bed1e5509f24c229ae2366cccbe7d4bcc6fc9ab0a188743be5ed737e74b04bece1f2add13bbf5295378527eed932"
    "1a220bc16cf5224f4a955802cec68927542796a1d9f74b9430461e6428561a9768c2fec228f702742280c441985f19a29"
    "c5cef8bf360acf290953544a33c72488e1ea5531c74ae09cfdb4db1f2c85d7c25b28eb31e749f576f36c564f7376f4dd1"
    "aefc00b668e45eea9431850c2af1fe1c7bf1a640dd4640f72da023482884c317a911075a5d48b10473348997adab48ebd"
    "ca8b9c0679c1bcd24c178d18d580091b1543059a358734a5ec562b5516d625ae2eba740951429b18cd4f5bcbb43671b97"
    "253257825003d9ef191c1583025de213e051767c6d37cc6cd9af051cb7baaed79d6515a6d305038f87f3bc4fdb27e2e4e"
    "9f945d4147cecd87a34b55051eb371e3c52370e6d2ae4e05ca5832383bfa09d81cf8ab2a61dddcf1e71716a49cd19771e"
    "f0e0a1265130cbfc9a5c8809ef62a5ff701587d6fa2f84c67f3e11ce5df940ad97bb8e9eb0ec688fe152c6c0b520b58a4"
    "a3a54b39281ccac5c09853fe0de373c25ad2f26085f9163ef16bb51d42b622e16ee7fb7c16cff10da11f981ac973a9d2f"
    "7d37a1a845fdbf3ad0377c8b01d46e4372b900fd07dde79030c74649906e28d219a723958adc45bf870cba074612a5408"
    "2360df1c4f59114728f965c98176d216da23573f57b11cf8ccffdb6443f81c83977e7fe9fbcba9a4497a02aede5dd647f"
    "742551614fb84d848d36f032ea3e9096ead45932c0e7e45d3a9e4fb95533b7f84d0b0d4ec85042e0dc94aa4c2670864b9"
    "f8073fd650cafbea88860288c35f89b608a6b8b2d6f5a49a270c5f9ce7e4ca06e1ecd0ad3a57091413f53f34b2fbf9b5e"
    "143706d1542d5f40fd9deeabc74df26acdd8b273ab1ad9811ba55b4466129c465e88897d01c9e7b27bc4025b66a5d63dd"
    "61dee1b4c86cff1e9fb88153a541dba90968f70800142f876568e50f4c7f44c56555e9f9dcdce3984518c5bb10f8a8153"
    "f879a0bbb032b881eb81baf0c669536e929896d3171323fd7078fb4a490ce282c6f685d92fbd98b9b905de7ac36f44328"
    "cb4419139396b1d47b056e17e9798a9e80c5126c15f462810b1c7895794dd3efc2d6f90bf4f1c062dc3501b65bf41df03"
    "7b79ab4c833ab1e6608567565e01d87357634ba09079658fdf80ee8a9a0df051a05a2047f05f0264b729cf7eba81d004b"
    "3a707c9d43c90549c1ce5b470ba51bb32373bd6dd73c3fd1b6e857e62d1ddc64778cc1e95a9936214ac79d036f663ceea"
    "8eaf069a708c744daeb185d9da3355b36a03aec25468d14a8f43e1e0e058c72e5564c4a9f25af8519750a781430998994"
    "038ce6206cf45ba094a87ffa8c003c24875c804a611515a94be79baa2341de97ae16daac9bb28a0327420701f4241bd162"
    "0bcefd1e6b190b9f35881c3860146facbbbc40c51c57fa83c8eda711c79eaffbc2c74376d0a7f8159f864487ed1e16d29"
    "ca68c2e007bdb98d09a0a6af0070874537f759de1168615b7cbd9f2c9aac0440f8e7bcd9d6fa4bdcc7d157a59612df796"
    "3cee5600"
)
V4_EP = (
    "Pd6g1a45vL1Y34ssEr8chqwLtuB3FmAR7c5QiRVwJl6QbhfubFJ6pJwt8jIOk1G+MMNBZDrT+QYM3D2ruR/4qCit24oLYDQVk"
    "B619CtNVToVp3epdI+Vs+83TzC4TqDXU18jGqMQJgA3f+GIwMWduJpCh+Tm26BiBdasrIE3I2w="
)
ORG_ID = "UWXspnCCJN4sfYlNfqps"


async def get_dId() -> str:
    async with httpx.AsyncClient() as client:
        json = {
            "appId": "default",
            "organization": ORG_ID,
            "os": "web",
            "orgId": ORG_ID,
            "data": V4_DATA,
            "ep": V4_EP,
            "encode": 5,
            "compress": 2,
        }
        response = await client.post(V4_URL, json=json)
        response.raise_for_status()
        data = response.json()
        status = data.get("code")
        if status != 1100:
            raise RequestException(f"获取 dId 失败：{data.get('msg')}")

        detail = data.get("detail") or {}
        device_id = detail.get("deviceId")
        if not device_id:
            raise RequestException("deviceId 缺失或无效")
        return f"B{device_id}"
