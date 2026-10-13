# Private container deployment

The HTTP entry point binds only to `127.0.0.1:8000`. It is intended for a tunnel
client running inside the same container. It does not implement authentication
for public or LAN exposure; keep the loopback binding.

Install the project in `~/poly-moodle` as the dedicated `agent` user. Create the
Linux `.venv`, install `requirements.txt`, and transfer `.moodle_token` privately.
Set the token's permissions to `600`.

Install the user service:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/poly-moodle.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now poly-moodle.service
```

Root must enable lingering once so this user service starts at container boot
and survives logout:

```bash
loginctl enable-linger agent
```

Manage and test the service as `agent` without sudo:

```bash
systemctl --user status poly-moodle.service
systemctl --user restart poly-moodle.service
journalctl --user -u poly-moodle.service -n 30
~/poly-moodle/.venv/bin/python ~/poly-moodle/deploy/check_server.py
```

For ChatGPT, configure the separate OpenAI Secure MCP Tunnel client to use
`http://127.0.0.1:8000/mcp` as its upstream HTTP MCP server. That client needs
its own tunnel ID and runtime API key, and should also run as a boot-time user
service. Installing this connector alone does not register a ChatGPT plugin.
