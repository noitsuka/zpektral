from typing import Any

import orjson
from fastapi.responses import Response


class RespostaJson(Response):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return orjson.dumps(content)
