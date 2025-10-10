# 🌼 Flower Installer
> Automate Celery Flower installation and deployment with Apache *or* Nginx, SSL (Certbot), Basic Auth, and systemd — all in one command.

![License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![Status](https://img.shields.io/badge/status-stable-brightgreen.svg)

**Flower Installer** provides a one-command setup (`flowerctl`) that installs and secures the Celery Flower dashboard with a reverse proxy (Apache or Nginx), optional SSL via Let's Encrypt (Certbot), Basic Authentication, and a systemd service. Perfect for production servers on Ubuntu/Debian.

---

> 🔗 **TLDR: Quick Install**
> ```bash
> pip install git+https://github.com/beachcitiessoftware/flower-installer.git
> sudo flowerctl install --domain www.yourdomain.com \
>   --app-dir /var/www/vhosts/flower-server \
>   --redis-url redis://127.0.0.1:6379/0 --certbot
> ```
> 🌐 Visit: https://www.yourdomain.com 
> 🧹 Uninstall: `sudo flowerctl uninstall`

## ✨ Features
- 🚀 One-command setup for Celery Flower
- 🧱 Auto-creates app folder and virtual environment
- 📦 Installs Celery + Flower into the venv
- 🔐 Optional Basic Auth login + IP restrictions
- 🌐 Apache or Nginx reverse proxy (your choice)
- 🔑 Optional SSL via Certbot (`--certbot`)
- ⚙️ Creates / manages a systemd service
- 🧹 Clean uninstallation (`flowerctl uninstall`)

## ⚠️ Prerequisites (on the server)
- **Python 3.8+**
- **Apache 2** *or* **Nginx**
- **Redis Server**
- **Certbot** (if you pass `--certbot`), with relevant plugin: `certbot-apache` or `certbot-nginx`
- **htpasswd** utility (for Basic Auth): package `apache2-utils` provides it on Debian/Ubuntu
- DNS A/AAAA record for your domain pointing to this server

## 🛠️ Install the CLI
```bash
pip install git+https://github.com/beachcitiessoftware/flower-installer.git
```

## 🚀 Usage
### Install Flower
```bash
sudo flowerctl install \
  --web-server apache \
  --domain www.yourdomain.com \
  --app-dir /var/www/vhosts/flower-server \
  --redis-url redis://127.0.0.1:6379/0 \
  --redis-backend-url redis://127.0.0.1:6379/1 \
  --create-user admin \
  --ip-allow 192.168.0.1,192.168.0.2 \
  --certbot
```
(Use `--web-server nginx` to configure Nginx instead of Apache.)

### Uninstall
```bash
sudo flowerctl uninstall
pip uninstall flower-installer
```

## 🧰 CLI Help
```bash
flowerctl                    # shows top-level help
flowerctl install --help     # show install options
```

## 📦 What it does
1. Creates the application directory and a Python virtualenv (`.venv`)
2. Installs Celery + Flower into that venv
3. Writes and enables the web server config (Apache or Nginx) as a reverse proxy to Flower on localhost
4. (Optional) Runs Certbot to install and configure SSL for your domain
5. Writes and enables a systemd service (`flower.service`) and starts it

## 🔐 Security
- You can combine IP restrictions and Basic Auth
- Flower binds to **127.0.0.1:5555**; only your web server can access it directly
- Consider restricting access to a VPN/admin IP list

## 🧑‍💻 Dev install
```bash
git clone https://github.com/beachcitiessoftware/flower-installer.git
cd flower-installer
pip install -e .
```

## 📜 License
MIT — see [LICENSE](LICENSE).
