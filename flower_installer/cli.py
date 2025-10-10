import argparse, subprocess, sys, shutil, os
from pathlib import Path
from getpass import getpass
from jinja2 import Template

TEMPLATES = Path(__file__).parent / "templates"


def run(cmd, **kw):
    print(f"→ {cmd}")
    subprocess.run(cmd, shell=True, check=True, **kw)


def render(name, **ctx):
    templ_path = TEMPLATES / name
    text = templ_path.read_text()
    return Template(text).render(**ctx)


def ensure_root():
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("This command must be run as root (sudo).")
        sys.exit(1)


def which_or_fail(binary, install_hint):
    if shutil.which(binary) is None:
        print(f"Missing required dependency: {binary}. {install_hint}")
        sys.exit(1)


def create_htpasswd(user, web_server):
    # choose path based on web server
    path = f"/etc/{'apache2' if web_server == 'apache' else 'nginx'}/flower_htpasswd"
    pw = getpass(f"Enter password for {user}: ")
    flag = "-c" if not Path(path).exists() else ""
    which_or_fail("htpasswd", "Install with: apt-get install apache2-utils")
    run(f"htpasswd {flag} -b {path} {user} {pw}")
    return path


def setup_apache(domain, ip_allow, use_auth):
    conf = render("flower.conf.j2", domain=domain, ip_allow=ip_allow, use_auth=use_auth)
    Path("/etc/apache2/sites-available/flower.conf").write_text(conf)
    run("a2enmod proxy proxy_http proxy_wstunnel headers")
    run("a2ensite flower")
    run("systemctl reload apache2")
    print(f"✅ Apache vhost created for http://{domain}")


def setup_nginx(domain, ip_allow, use_auth):
    conf = render("flower.nginx.j2", domain=domain, ip_allow=ip_allow, use_auth=use_auth)
    Path("/etc/nginx/sites-available/flower").write_text(conf)
    # ensure sites-enabled symlink
    enabled = Path("/etc/nginx/sites-enabled/flower")
    if enabled.exists() or enabled.is_symlink():
        try:
            enabled.unlink()
        except Exception:
            pass
    enabled.symlink_to(Path("/etc/nginx/sites-available/flower"))
    run("nginx -t")
    run("systemctl reload nginx")
    print(f"✅ Nginx server block created for http://{domain}")


def issue_cert(domain, web_server):
    # certbot must be installed system-wide
    which_or_fail("certbot", "Install with: apt-get install certbot python3-certbot-apache|nginx")
    plugin = "--apache" if web_server == "apache" else "--nginx"
    run(f"certbot {plugin} -d {domain} --non-interactive --agree-tos -m admin@{domain}")
    print(f"✅ SSL certificate issued for https://{domain}")


def create_app_dir_and_venv(app_dir):
    Path(app_dir).mkdir(parents=True, exist_ok=True)
    venv = Path(app_dir) / ".venv"
    run(f"python3 -m venv {venv}")
    run(f"{venv}/bin/pip install --upgrade pip setuptools wheel")
    # Install only runtime deps inside the venv
    run(f"{venv}/bin/pip install celery flower")
    print(f"✅ Created venv at {venv} and installed celery+flower")
    return str(venv)


def write_systemd(app_dir, redis_url):
    service = render("flower.service.j2", project_dir=app_dir, venv=f"{app_dir}/.venv", redis_url=redis_url)
    Path("/etc/systemd/system/flower.service").write_text(service)
    run("systemctl daemon-reload")
    run("systemctl enable flower")
    run("systemctl restart flower")
    print("✅ Flower systemd service enabled and started")


def uninstall():
    print("🧹 Uninstalling Flower...")
    # Stop and disable
    run("systemctl stop flower || true")
    run("systemctl disable flower || true")
    # Remove service
    Path("/etc/systemd/system/flower.service").unlink(missing_ok=True)
    # Remove Apache/Nginx config
    if Path("/etc/apache2/sites-available/flower.conf").exists():
        run("a2dissite flower || true")
        Path("/etc/apache2/sites-available/flower.conf").unlink(missing_ok=True)
        run("systemctl reload apache2 || true")
    if Path("/etc/nginx/sites-enabled/flower").exists() or Path("/etc/nginx/sites-available/flower").exists():
        Path("/etc/nginx/sites-enabled/flower").unlink(missing_ok=True)
        Path("/etc/nginx/sites-available/flower").unlink(missing_ok=True)
        run("nginx -t || true")
        run("systemctl reload nginx || true")
    print("✅ Uninstalled Flower service and web server config")


def main():
    parser = argparse.ArgumentParser(prog="flowerctl", description="Manage Celery Flower dashboard (Apache or Nginx)")
    sub = parser.add_subparsers(dest="cmd")

    install_cmd = sub.add_parser("install", help="Install and configure Flower")
    install_cmd.add_argument("--web-server", choices=["apache", "nginx"], default="apache",
                             help="Web server to configure (default: apache)")
    install_cmd.add_argument("--domain", help="Domain name for Flower dashboard (e.g., tracking.fitness)")
    install_cmd.add_argument("--app-dir",
                             help="Directory to install the venv and run Flower (e.g., /var/www/vhosts/flower-server)")
    install_cmd.add_argument("--redis-url", help="Redis broker URL (e.g., redis://127.0.0.1:6379/0)")
    install_cmd.add_argument("--ip-allow", default="", help="Comma-separated list of allowed IPs (optional)")
    install_cmd.add_argument("--create-user", help="Username for Basic Auth (optional)")
    install_cmd.add_argument("--certbot", action="store_true", help="Automatically issue SSL cert via Certbot")

    sub.add_parser("uninstall", help="Remove Flower configs and service")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.cmd == "install":
        ensure_root()
        # Validate required args for install
        if not args.domain or not args.app_dir or not args.redis_url:
            print("\nUsage: flowerctl install --domain <domain> --app-dir <dir> --redis-url <url> [options]\n")
            sys.exit(1)

        venv = create_app_dir_and_venv(args.app_dir)

        use_auth = False
        if args.create_user:
            create_htpasswd(args.create_user, args.web_server)
            use_auth = True

        if args.web_server == "nginx":
            setup_nginx(args.domain, args.ip_allow, use_auth)
        else:
            setup_apache(args.domain, args.ip_allow, use_auth)

        if args.certbot:
            issue_cert(args.domain, args.web_server)

        write_systemd(args.app_dir, args.redis_url)

        print(f"\n🎉 Flower dashboard running at https://{args.domain}")
        if use_auth:
            print(f"Login user: {args.create_user}")

    elif args.cmd == "uninstall":
        ensure_root()
        uninstall()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
