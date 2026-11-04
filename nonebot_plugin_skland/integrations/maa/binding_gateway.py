"""Start by module directory; never import the bot package or its configuration."""

import os

from binding_rpc import client
from binding_web import create_app

app = create_app(client(os.environ["MAA_BINDING_SOCKET"]), os.environ["MAA_PUBLIC_URL"].rstrip("/"))
