import argparse
import ipaddress
import os
import shutil
import subprocess
import sys
from getpass import getpass
from pathlib import Path
from typing import Optional

from jinja2 import Template

TEMPLATES = Path(__file__).parent / "templates"


def validate_ip_list(ip_list: str) -> Optional[str]:
    """
    Validates IP addresses to ensure they are valid.
    :param ip_list: The IP addresses to validate.
    :return: A list of valid IP addresses
    """
    if not ip_list:
        return None
    ips = [i.strip() for i in ip_list.split(",") if i.strip()]
    for ip in ips:
        try:
            ipaddress.ip_network(ip, strict=False)
        except ValueError:
            print(f"❌ Invalid IP address or network: {ip}")
            sys.exit(1)
    return ",".join(ips)


def run(cmd: str, **kw) -> None:
    """
    Run a command and capture its output.
    :param cmd: The command to run.
    :param kw: Command arguments to pass to subprocess.
    :return: The response from the command.
    """
    print(f"→ {cmd}")
    try:
        subprocess.run(cmd, shell=True, check=True, **kw)
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {cmd}")
        sys.exit(e.returncode)


def render(name: str, **ctx) -> str:
    """
    Render jinja templates.
    :param name: The name of the template.
    :param ctx: Arguments to pass to jinja templates.
    :return: The rendered template.
    """
    templ_path = TEMPLATES / name
    text = templ_path.read_text()
    # Special handling for nginx ip_allow splitting into multiple allow lines
    if name.endswith("flower.nginx.j2") and ctx.get("ip_allow") and "," in ctx["ip_allow"]:
        ips = [ip.strip() for ip in ctx["ip_allow"].split(",") if ip.strip()]
        allow_lines = "\n".join(f"allow {ip};" for ip in ips)
        ctx = dict(ctx)
        ctx["ip_allow"] = allow_lines
    return Template(text).render(**ctx)


def ensure_root() -> None:
    """
    Ensures the user has sudo privileges.
    :return:
    """
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("This command must be run as root (sudo).")
        sys.exit(1)


def which_or_fail(binary: str, install_hint: str) -> None:
    """
    Performs a which on the binary to ensure it is installed.
    :param binary: The name of the binary.
    :param install_hint: A hint to tell user how to install the missing binary on failure.
    :return:
    """
    if shutil.which(binary) is None:
        print(f"Missing required dependency: {binary}. {install_hint}")
        sys.exit(1)


def create_htpasswd(user: str, web_server: str) -> str:
    """
    Creates a htpasswd file for the given user.
    :param user: The user to create the htpasswd file for.
    :param web_server: The web server to create the htpasswd file for.
    :return: Returns the path to the created htpasswd file.
    """
    # choose path based on web server
    path = f"/etc/{'apache2' if web_server == 'apache' else 'nginx'}/flower_htpasswd"
    pw = getpass(f"Enter password for {user}: ")
    flag = "-c" if not Path(path).exists() else ""
    which_or_fail("htpasswd", "Install with: apt-get install apache2-utils")
    run(f"htpasswd {flag} -b {path} {user} {pw}")
    return path


def setup_apache(domain: str, ip_allow: Optional[str], use_auth: bool) -> None:
    """
    Sets up an apache2 host for the flower server.
    :param domain: The domain name to use in the config file.
    :param ip_allow: Optional list of IP addresses to allow.
    :param use_auth: Whether to require basic authentication, or not.
    :return:
    """
    conf = render("flower.conf.j2", domain=domain, ip_allow=ip_allow, use_auth=use_auth)
    Path("/etc/apache2/sites-available/flower.conf").write_text(conf)
    run("a2enmod proxy proxy_http proxy_wstunnel headers")
    run("a2ensite flower")
    run("systemctl reload apache2")
    print(f"✅ Apache vhost created for http://{domain}")


def setup_nginx(domain: str, ip_allow: Optional[str], use_auth: bool) -> None:
    """
    Sets up a nginx host for the flower server.
    :param domain: The domain name to use in the config file.
    :param ip_allow: Optional list of IP addresses to allow.
    :param use_auth: Whether to require basic authentication, or not.
    :return:
    """
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


def issue_cert(domain: str, web_server: str) -> None:
    """
    Uses certbot to issue a SSL cert for the given domain.
    :param domain: The domain to issue a SSL cert for.
    :param web_server: The web server to issue a SSL cert for: (apache | nginx)
    :return:
    """
    # certbot must be installed system-wide
    which_or_fail("certbot", "Install with: apt-get install certbot python3-certbot-apache|nginx")
    plugin = "--apache" if web_server == "apache" else "--nginx"
    run(f"certbot {plugin} -d {domain} --non-interactive --agree-tos -m admin@{domain}")
    print(f"✅ SSL certificate issued for https://{domain}")


def create_app_dir_and_venv(app_dir: str) -> str:
    """
    Creates the app directory and venv for the flower server.
    :param app_dir:
    :return:
    """
    Path(app_dir).mkdir(parents=True, exist_ok=True)
    venv = Path(app_dir) / ".venv"
    run(f"python3 -m venv {venv}")
    run(f"{venv}/bin/pip install --upgrade pip setuptools wheel")
    # Install only runtime deps inside the venv
    run(f"{venv}/bin/pip install celery[redis] flower")
    print(f"✅ Created venv at {venv} and installed celery+flower")
    return str(venv)


def write_systemd(app_dir: str, redis_url: str) -> None:
    """
    Creates a systemd file for the flower server.
    :param app_dir: The directory where the flower app's venv is installed.
    :param redis_url: The URL of the redis database.
    :return:
    """
    service = render("flower.service.j2", project_dir=app_dir, venv=f"{app_dir}/.venv", redis_url=redis_url)
    Path("/etc/systemd/system/flower.service").write_text(service)
    run("systemctl daemon-reload")
    run("systemctl enable flower")
    run("systemctl restart flower")
    print("✅ Flower systemd service enabled and started")


def uninstall(args: argparse.Namespace) -> None:
    """
    Uninstalls the flower server.
    :param args:
    :return:
    """
    ensure_root()
    print("🧹 Uninstalling Flower...")
    # Stop and disable
    run("systemctl stop flower || true")
    run("systemctl disable flower || true")
    # Remove service
    Path("/etc/systemd/system/flower.service").unlink(missing_ok=True)

    # Remove Apache/Nginx config
    if Path("/etc/apache2/sites-available/flower.conf").exists():
        run("a2dissite flower || true")
        if not args.keep_site:
            Path("/etc/apache2/sites-available/flower.conf").unlink(missing_ok=True)
        run("systemctl reload apache2 || true")
    if Path("/etc/nginx/sites-enabled/flower").exists() or Path("/etc/nginx/sites-available/flower").exists():
        Path("/etc/nginx/sites-enabled/flower").unlink(missing_ok=True)
        if not args.keep_site:
            Path("/etc/nginx/sites-available/flower").unlink(missing_ok=True)
        run("nginx -t || true")
        run("systemctl reload nginx || true")
    print("✅ Uninstalled Flower service and web server config")


def install(args: argparse.Namespace) -> None:
    """
    Installs the flower server.
    :param args:
    :return:
    """
    ensure_root()
    # Validate required args for install
    if not args.domain or not args.app_dir or not args.redis_url:
        print("\nUsage: flowerctl install --domain <domain> --app-dir <dir> --redis-url <url> [options]\n")
        sys.exit(1)

    args.ip_allow = validate_ip_list(args.ip_allow)

    app_dir = str(args.app_dir).rstrip("/")
    venv = create_app_dir_and_venv(app_dir)

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

    write_systemd(app_dir, args.redis_url)

    print(f"\n🎉 Flower dashboard running at https://{args.domain}")
    if use_auth:
        print(f"Login user: {args.create_user}")


def main() -> None:
    """
    Main entry point.
    :return:
    """
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

    uninstall_cmd = sub.add_parser("uninstall", help="Remove Flower configs and service")
    uninstall_cmd.add_argument("--keep-site", action="store_true", help="Keep Apache/Nginx config, but disable it.")

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    if args.cmd == "install":
        install(args)
    elif args.cmd == "uninstall":
        uninstall(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
