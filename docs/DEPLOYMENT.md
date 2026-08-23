# Production Deployment

This runbook prepares a Debian or Ubuntu host for deployment through `.github/workflows/deploy.yml`.

The application uses Telegram long polling. Only SSH must be reachable from the internet. Redis and the bot do not need public ports.

## Target layout

```text
deploy user
  /opt/unpaywallbot
    .env.production
    docker-compose.yml
    repository checkout

rootless Docker
  unpaywallbot-bot
  unpaywallbot-redis
  private backend network
  outbound bot network
```

## 1. Patch the host

Run as root:

```bash
apt-get update
apt-get dist-upgrade -y
apt-get install -y \
  ca-certificates \
  curl \
  fail2ban \
  git \
  gnupg \
  uidmap \
  ufw \
  unattended-upgrades
```

Enable automatic security updates:

```bash
dpkg-reconfigure -plow unattended-upgrades
systemctl enable --now unattended-upgrades
```

## 2. Create the deployment user

```bash
adduser --disabled-password --gecos "" deploy
loginctl enable-linger deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
install -d -m 755 -o deploy -g deploy /opt/unpaywallbot
```

Do not add `deploy` to the `sudo` or `docker` group. Access to a rootful Docker socket is effectively root access.

## 3. Configure key-only SSH

Create a dedicated Ed25519 key on a trusted workstation or CI administration machine:

```bash
ssh-keygen -t ed25519 -a 100 \
  -f unpaywallbot_deploy \
  -C unpaywallbot-github-actions
```

Install the public key:

```bash
install -m 600 -o deploy -g deploy \
  unpaywallbot_deploy.pub \
  /home/deploy/.ssh/authorized_keys
```

Create `/etc/ssh/sshd_config.d/10-hardening.conf`:

```text
PermitRootLogin no
PasswordAuthentication no
KbdInteractiveAuthentication no
PubkeyAuthentication yes
AllowUsers deploy
MaxAuthTries 3
LoginGraceTime 30
X11Forwarding no
AllowAgentForwarding no
PermitTunnel no
```

Validate before reloading:

```bash
sshd -t
systemctl reload ssh
```

Keep the existing root session open until a second terminal confirms that key-based login as `deploy` works.

## 4. Firewall

Replace `22` if SSH uses another port:

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment "SSH"
ufw enable
ufw status verbose
```

Do not open ports 6379, 80, 443, or application-specific ports for this long-polling bot.

## 5. Fail2ban

Create `/etc/fail2ban/jail.d/sshd.local`:

```ini
[sshd]
enabled = true
backend = systemd
port = 22
maxretry = 5
findtime = 10m
bantime = 1h
bantime.increment = true
```

Then:

```bash
systemctl enable --now fail2ban
fail2ban-client status sshd
```

## 6. Install rootless Docker

Install Docker Engine from the official Docker repository, including `docker-ce-rootless-extras`. Then run as `deploy`:

```bash
sudo -iu deploy
dockerd-rootless-setuptool.sh install
```

Add the values printed by the installer to `/home/deploy/.profile`. They normally include:

```bash
export PATH="$HOME/bin:$PATH"
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
```

Verify:

```bash
docker info
docker compose version
docker run --rm hello-world
```

The deployment workflow detects the rootless socket at `/run/user/<uid>/docker.sock`.

## 7. Clone the repository

As `deploy`:

```bash
git clone https://github.com/anfixit/unpaywallbot.git \
  /opt/unpaywallbot
cd /opt/unpaywallbot
git checkout main
```

Create an initial environment file so Compose validation can run:

```bash
cp .env.example .env.production
chmod 600 .env.production
```

Do not put real production secrets into the repository checkout manually if GitHub Actions will manage the file.

## 8. Protect the GitHub production environment

Create a GitHub Environment named `production`.

Recommended environment protection:

- restrict deployment branches to `main`
- require manual approval for the first deployments
- prevent administrators from bypassing protection when practical
- keep `DEPLOY_ENABLED` set to `false` until bootstrap is complete

Create repository variable:

| Variable | Value |
| --- | --- |
| `DEPLOY_ENABLED` | `false` initially, then `true` |

Create production environment secrets:

| Secret | Purpose |
| --- | --- |
| `SSH_HOST` | Server address |
| `SSH_PORT` | SSH port, normally `22` |
| `SSH_USER` | `deploy` |
| `SSH_PRIVATE_KEY` | Complete private deployment key |
| `SSH_KNOWN_HOSTS` | Verified OpenSSH host-key line |
| `DEPLOY_PATH` | `/opt/unpaywallbot` |
| `BOT_TOKEN` | Telegram bot token |
| `ENCRYPTION_KEY` | Random secret with at least 32 characters |
| `ALLOWED_USERS` | JSON array such as `[123456789]` |
| `PUBLIC_ACCESS` | Normally `false` |

The workflow uses the run's own `GITHUB_TOKEN` both to publish the image and
to authenticate the server for the pull, then logs the server out of GHCR
again. No separate `GHCR_USERNAME` or `GHCR_TOKEN` secret is required.

`SSH_PORT`, `SSH_KNOWN_HOSTS`, and `PUBLIC_ACCESS` are optional. Without
`SSH_KNOWN_HOSTS` the workflow falls back to `ssh-keyscan`, which trusts the
host key on first use — set the verified line before the first real
deployment.

### Notification secrets

Build and deployment results are reported to Telegram. These two values are
**repository** secrets, not `production` environment secrets, because the
notification jobs do not join the protected environment:

| Repository secret | Purpose |
| --- | --- |
| `TELEGRAM_NOTIFICATION_TOKEN` | Token of the notification bot |
| `TELEGRAM_NOTIFICATION_CHAT_ID` | Chat that receives the reports |

Both workflows notify `@gitanfinotification_bot`. The deployment workflow
fails when the values are missing, and `CI` fails on `main` and warns on
pull requests, so a silently missing notification cannot go unnoticed.

## 9. Verify the SSH host key

Obtain the server fingerprint through a trusted channel:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Compare it with the client result. Only after verification, store the complete `known_hosts` line in `SSH_KNOWN_HOSTS`.

Do not trust an unverified `ssh-keyscan` result by itself.

## 10. First deployment

1. Merge a pull request only after all `CI` jobs pass.
2. Confirm the `Build and deploy` workflow publishes the image.
3. Set `DEPLOY_ENABLED=true`.
4. Run `Build and deploy` manually for the first deployment.
5. Approve the protected environment if approval is enabled.

The workflow will:

1. publish `ghcr.io/anfixit/unpaywallbot:<commit-sha>`
2. upload `.env.production.next`
3. authenticate the server to GHCR
4. reset the deployment checkout to the validated `main`
5. atomically activate `.env.production`
6. pull the immutable image tag
7. run `docker compose up -d`
8. execute the container healthcheck

## 11. Verification

On the server:

```bash
cd /opt/unpaywallbot
docker compose ps
docker compose logs --tail=100 bot
docker compose exec -T bot python -m bot.healthcheck
docker compose exec -T redis redis-cli ping
ss -lntup
```

Expected results:

- bot and Redis are healthy
- Redis returns `PONG`
- no process listens publicly on port 6379
- no application HTTP port is open
- Telegram `/start` and `/help` work
- an invalid or private URL is rejected
- a public article request completes or returns a controlled error

## 12. Rollback

Find a previously published commit-SHA tag in GHCR, then on the server:

```bash
cd /opt/unpaywallbot
export BOT_IMAGE=ghcr.io/anfixit/unpaywallbot:<previous-sha>
docker compose pull bot
docker compose up -d --no-deps bot
docker compose exec -T bot python -m bot.healthcheck
```

Do not roll back `.env.production` unless configuration changed. Keep a separately protected backup of the previous environment file if a deployment modifies configuration.

## 13. Redis backup

Before risky upgrades:

```bash
cd /opt/unpaywallbot
docker compose exec -T redis redis-cli SAVE
docker run --rm \
  -v unpaywallbot_redis_data:/data:ro \
  -v "$PWD/backups:/backup" \
  alpine \
  tar -czf /backup/redis-$(date +%F-%H%M%S).tar.gz -C /data .
```

Store backups outside the host when Redis data becomes operationally important.

## 14. Credential rotation

Rotate immediately after suspected exposure:

- Telegram bot token through BotFather
- deployment SSH key
- GHCR token
- `ENCRYPTION_KEY`, with a migration plan for encrypted state
- server root and user passwords if they were shared insecurely

After rotation, update GitHub Environment secrets and run a controlled deployment.
