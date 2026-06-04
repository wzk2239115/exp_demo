"""Unit tests for cybergym.firewall.proxy module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cybergym.firewall.proxy import (
    DEFAULT_ALLOWLIST_PATH,
    INTERNAL_NETWORK,
    PROXY_CONTAINER_NAME,
    PROXY_IMAGE,
    PROXY_PORT,
    FirewallProxyManager,
    load_allowlist,
)


class TestLoadAllowlist:
    """Tests for load_allowlist()."""

    def test_load_basic_domains(self, tmp_path):
        """Test loading a simple allowlist file."""
        f = tmp_path / "allowlist.txt"
        f.write_text("example.com\npypi.org\n")
        domains = load_allowlist(f)
        assert domains == ["example.com", "pypi.org"]

    def test_preserves_squid_format(self, tmp_path):
        """Test that leading dots (Squid dstdomain format) are preserved."""
        f = tmp_path / "allowlist.txt"
        f.write_text(".example.com\n.pypi.org\nplain.org\n")
        domains = load_allowlist(f)
        assert domains == [".example.com", ".pypi.org", "plain.org"]

    def test_ignores_blank_lines(self, tmp_path):
        """Test that empty and whitespace-only lines are skipped."""
        f = tmp_path / "allowlist.txt"
        f.write_text("example.com\n\n   \npypi.org\n")
        domains = load_allowlist(f)
        assert domains == ["example.com", "pypi.org"]

    def test_ignores_comments(self, tmp_path):
        """Test that lines starting with # are skipped."""
        f = tmp_path / "allowlist.txt"
        f.write_text("# This is a comment\nexample.com\n# Another comment\npypi.org\n")
        domains = load_allowlist(f)
        assert domains == ["example.com", "pypi.org"]

    def test_strips_whitespace(self, tmp_path):
        """Test that leading/trailing whitespace is stripped from domains."""
        f = tmp_path / "allowlist.txt"
        f.write_text("  example.com  \n  .pypi.org  \n")
        domains = load_allowlist(f)
        assert domains == ["example.com", ".pypi.org"]

    def test_empty_file(self, tmp_path):
        """Test loading an empty file returns empty list."""
        f = tmp_path / "allowlist.txt"
        f.write_text("")
        domains = load_allowlist(f)
        assert domains == []

    def test_comments_only(self, tmp_path):
        """Test loading a file with only comments returns empty list."""
        f = tmp_path / "allowlist.txt"
        f.write_text("# just comments\n# nothing else\n")
        domains = load_allowlist(f)
        assert domains == []

    def test_accepts_string_path(self, tmp_path):
        """Test that a string path works in addition to Path objects."""
        f = tmp_path / "allowlist.txt"
        f.write_text("example.com\n")
        domains = load_allowlist(str(f))
        assert domains == ["example.com"]

    def test_file_not_found(self):
        """Test that a missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_allowlist("/nonexistent/path/allowlist.txt")

    def test_real_allowlist_file(self):
        """Test loading the reference allowlist from the repo."""
        path = (
            Path(__file__).resolve().parents[2]
            / "tmp"
            / "proxy_impl"
            / "allow_domains.txt"
        )
        if not path.exists():
            pytest.skip("Reference allowlist file not present")
        domains = load_allowlist(path)
        assert len(domains) == 10
        assert ".pypi.org" in domains
        assert ".archive.ubuntu.com" in domains

    def test_default_allowlist_file_exists(self):
        """Test that the default allowlist file shipped with the module exists."""
        assert DEFAULT_ALLOWLIST_PATH.exists()

    def test_default_allowlist_loads(self):
        """Test that the default allowlist file can be loaded and is non-empty."""
        domains = load_allowlist(DEFAULT_ALLOWLIST_PATH)
        assert len(domains) > 0


class TestFirewallProxyManagerInit:
    """Tests for FirewallProxyManager constructor and default values."""

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_default_allowlist(self, mock_docker):
        """Test that the default allowlist file is used when none specified."""
        mgr = FirewallProxyManager()
        assert mgr.allowlist_path == DEFAULT_ALLOWLIST_PATH.resolve()

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_custom_allowlist(self, mock_docker, tmp_path):
        """Test that a custom allowlist path is accepted."""
        f = tmp_path / "custom.txt"
        f.write_text(".example.com\n")
        mgr = FirewallProxyManager(allowlist_path=f)
        assert mgr.allowlist_path == f.resolve()

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_missing_allowlist_raises(self, mock_docker):
        """Test that a missing allowlist file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            FirewallProxyManager(allowlist_path="/nonexistent/file.txt")

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_extra_domains(self, mock_docker):
        """Test that extra domains are stored."""
        mgr = FirewallProxyManager(extra_domains=[".extra.com"])
        assert mgr.extra_domains == [".extra.com"]

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_default_ips(self, mock_docker):
        """Test that extra_ips defaults to empty list."""
        mgr = FirewallProxyManager()
        assert mgr.extra_ips == []

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_custom_ips(self, mock_docker):
        """Test setting extra IPs."""
        mgr = FirewallProxyManager(extra_ips=["10.0.0.1", "192.168.1.0/24"])
        assert mgr.extra_ips == ["10.0.0.1", "192.168.1.0/24"]

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_ip_allowlist_path(self, mock_docker, tmp_path):
        """Test setting an IP allowlist file."""
        f = tmp_path / "ips.txt"
        f.write_text("10.0.0.0/8\n")
        mgr = FirewallProxyManager(ip_allowlist_path=f)
        assert mgr.ip_allowlist_path == f.resolve()

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_missing_ip_allowlist_raises(self, mock_docker):
        """Test that a missing IP allowlist file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            FirewallProxyManager(ip_allowlist_path="/nonexistent/ips.txt")

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_default_constants(self, mock_docker):
        """Test default proxy image, port, container name, network name."""
        mgr = FirewallProxyManager()
        assert mgr.proxy_image == PROXY_IMAGE
        assert mgr.proxy_port == PROXY_PORT
        assert mgr.container_name == PROXY_CONTAINER_NAME
        assert mgr.network_name == INTERNAL_NETWORK

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_custom_network_name(self, mock_docker):
        """Test overriding the network name."""
        mgr = FirewallProxyManager(network_name="my-custom-net")
        assert mgr.network_name == "my-custom-net"


class TestFirewallProxyManagerEnvVars:
    """Tests for FirewallProxyManager.env_vars() and proxy_url."""

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_proxy_url(self, mock_docker):
        """Test that proxy_url is built from container name and port."""
        mgr = FirewallProxyManager()
        assert mgr.proxy_url == f"http://{PROXY_CONTAINER_NAME}:{PROXY_PORT}"

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_env_vars_keys(self, mock_docker):
        """Test that env_vars returns both upper and lower case proxy vars."""
        mgr = FirewallProxyManager()
        env = mgr.env_vars()
        assert "HTTP_PROXY" in env
        assert "HTTPS_PROXY" in env
        assert "NO_PROXY" in env
        assert "http_proxy" in env
        assert "https_proxy" in env
        assert "no_proxy" in env

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_env_vars_values(self, mock_docker):
        """Test that proxy env vars point to the correct URL."""
        mgr = FirewallProxyManager()
        env = mgr.env_vars()
        expected_url = f"http://{PROXY_CONTAINER_NAME}:{PROXY_PORT}"
        assert env["HTTP_PROXY"] == expected_url
        assert env["HTTPS_PROXY"] == expected_url
        assert env["http_proxy"] == expected_url
        assert env["https_proxy"] == expected_url

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_no_proxy_entries(self, mock_docker):
        """Test that NO_PROXY contains configured entries."""
        mgr = FirewallProxyManager(no_proxy=["localhost", "10.0.0.1"])
        env = mgr.env_vars()
        assert env["NO_PROXY"] == "localhost,10.0.0.1"
        assert env["no_proxy"] == "localhost,10.0.0.1"


class TestSquidConfGeneration:
    """Tests for the Squid configuration generation."""

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_domain_acl_references_file(self, mock_docker):
        """Test that domain ACL references the external allowlist file."""
        from cybergym.firewall.proxy import DOMAIN_ALLOWLIST_CONTAINER_PATH

        mgr = FirewallProxyManager()
        conf = mgr._generate_squid_conf()
        assert (
            f'acl allowed_domains dstdomain "{DOMAIN_ALLOWLIST_CONTAINER_PATH}"' in conf
        )

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_ip_acl_references_file(self, mock_docker):
        """Test that IP ACL references the external file when IPs are configured."""
        from cybergym.firewall.proxy import IP_ALLOWLIST_CONTAINER_PATH

        mgr = FirewallProxyManager(extra_ips=["10.0.0.1"])
        conf = mgr._generate_squid_conf()
        assert f'acl allowed_ips dst "{IP_ALLOWLIST_CONTAINER_PATH}"' in conf
        assert "http_access allow allowed_ips" in conf

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_ip_acl_with_file(self, mock_docker, tmp_path):
        """Test that IP ACL is enabled when ip_allowlist_path is set."""
        f = tmp_path / "ips.txt"
        f.write_text("10.0.0.0/8\n")
        mgr = FirewallProxyManager(ip_allowlist_path=f)
        conf = mgr._generate_squid_conf()
        assert "allowed_ips" in conf

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_no_ip_acls_when_empty(self, mock_docker):
        """Test that IP ACLs are absent when no IPs are configured."""
        mgr = FirewallProxyManager()
        conf = mgr._generate_squid_conf()
        assert "allowed_ips" not in conf

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_deny_all_present(self, mock_docker):
        """Test that deny-all rule is present."""
        mgr = FirewallProxyManager()
        conf = mgr._generate_squid_conf()
        assert "http_access deny all" in conf

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_cache_disabled(self, mock_docker):
        """Test that disk cache is disabled."""
        mgr = FirewallProxyManager()
        conf = mgr._generate_squid_conf()
        assert "cache deny all" in conf

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_port_in_config(self, mock_docker):
        """Test that the configured port appears in squid.conf."""
        mgr = FirewallProxyManager(proxy_port=8080)
        conf = mgr._generate_squid_conf()
        assert "http_port 8080" in conf

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_extra_ports_with_ips(self, mock_docker):
        """Test that all ports are opened when IPs are allowed."""
        mgr = FirewallProxyManager(extra_ips=["10.0.0.1"])
        conf = mgr._generate_squid_conf()
        assert "1-65535" in conf

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_no_extra_ports_without_ips(self, mock_docker):
        """Test that extra ports are not opened without IP allowlist."""
        mgr = FirewallProxyManager()
        conf = mgr._generate_squid_conf()
        assert "1-65535" not in conf


class TestBuildAllowlist:
    """Tests for FirewallProxyManager._build_allowlist()."""

    def test_file_only(self, tmp_path):
        """Test building allowlist from file alone."""
        f = tmp_path / "domains.txt"
        f.write_text("example.com\ntest.org\n")
        result = FirewallProxyManager._build_allowlist(f, [])
        assert result == "example.com\ntest.org\n"

    def test_extras_only(self):
        """Test building allowlist from extra entries alone."""
        result = FirewallProxyManager._build_allowlist(None, ["a.com", "b.com"])
        assert result == "a.com\nb.com\n"

    def test_file_plus_extras(self, tmp_path):
        """Test merging file and extra entries."""
        f = tmp_path / "domains.txt"
        f.write_text("from-file.com\n")
        result = FirewallProxyManager._build_allowlist(f, ["extra.com"])
        assert "from-file.com" in result
        assert "extra.com" in result

    def test_empty(self):
        """Test that no file and no extras returns empty string."""
        result = FirewallProxyManager._build_allowlist(None, [])
        assert result == ""


class TestFirewallProxyManagerNetworkOps:
    """Tests for FirewallProxyManager network and container lifecycle (mocked Docker)."""

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_ensure_network_creates_internal(self, mock_docker):
        """Test that _ensure_network creates an internal bridge network."""
        from docker.errors import NotFound

        client = MagicMock()
        mock_docker.return_value = client
        client.networks.get.side_effect = NotFound("not found")

        mgr = FirewallProxyManager()
        mgr._ensure_network()

        client.networks.create.assert_called_once_with(
            INTERNAL_NETWORK, driver="bridge", internal=True
        )

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_ensure_network_skips_existing_internal(self, mock_docker):
        """Test that _ensure_network accepts an existing internal network."""
        client = MagicMock()
        mock_docker.return_value = client
        net = MagicMock()
        net.attrs = {"Internal": True}
        client.networks.get.return_value = net

        mgr = FirewallProxyManager()
        mgr._ensure_network()

        client.networks.create.assert_not_called()

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_ensure_network_rejects_external(self, mock_docker):
        """Test that _ensure_network raises if existing network is not internal."""
        client = MagicMock()
        mock_docker.return_value = client
        net = MagicMock()
        net.attrs = {"Internal": False}
        client.networks.get.return_value = net

        mgr = FirewallProxyManager()
        with pytest.raises(RuntimeError, match="not internal"):
            mgr._ensure_network()

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_stop_removes_container(self, mock_docker):
        """Test that stop() force-removes the proxy container."""
        client = MagicMock()
        mock_docker.return_value = client
        container = MagicMock()
        client.containers.get.return_value = container

        mgr = FirewallProxyManager()
        mgr.stop()

        client.containers.get.assert_called_once_with(PROXY_CONTAINER_NAME)
        container.remove.assert_called_once_with(force=True)

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_stop_ignores_not_found(self, mock_docker):
        """Test that stop() does not raise when container doesn't exist."""
        from docker.errors import NotFound

        client = MagicMock()
        mock_docker.return_value = client
        client.containers.get.side_effect = NotFound("not found")

        mgr = FirewallProxyManager()
        mgr.stop()  # should not raise

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_host_gateway(self, mock_docker):
        """Test that host_gateway reads the gateway from network IPAM config."""
        client = MagicMock()
        mock_docker.return_value = client
        net = MagicMock()
        net.attrs = {"IPAM": {"Config": [{"Gateway": "172.18.0.1"}]}}
        client.networks.get.return_value = net

        mgr = FirewallProxyManager()
        assert mgr.host_gateway == "172.18.0.1"

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_host_gateway_raises_without_gateway(self, mock_docker):
        """Test that host_gateway raises when no gateway is configured."""
        client = MagicMock()
        mock_docker.return_value = client
        net = MagicMock()
        net.attrs = {"IPAM": {"Config": [{}]}}
        client.networks.get.return_value = net

        mgr = FirewallProxyManager()
        with pytest.raises(RuntimeError, match="No gateway found"):
            _ = mgr.host_gateway

    @patch("cybergym.firewall.proxy.docker.from_env")
    def test_status_no_infra(self, mock_docker):
        """Test status() when neither network nor proxy exist."""
        from docker.errors import NotFound

        client = MagicMock()
        mock_docker.return_value = client
        client.networks.get.side_effect = NotFound("not found")
        client.containers.get.side_effect = NotFound("not found")

        mgr = FirewallProxyManager()
        s = mgr.status()
        assert s["network"] is None
        assert s["proxy"] is None


class TestEvalConfigProxy:
    """Tests for proxy-related fields in EvalConfig and AgentFnArguments."""

    def test_eval_config_use_firewall_default(self):
        """Test that use_firewall defaults to False."""
        from cybergym.evaluation.types import EvalConfig

        config = EvalConfig(
            task_id="test", task_type="USER_EXPLOITATION", out_dir="/tmp/test"
        )
        assert config.use_firewall is False

    def test_eval_config_use_firewall_set(self):
        """Test setting use_firewall on EvalConfig."""
        from cybergym.evaluation.types import EvalConfig

        config = EvalConfig(
            task_id="test",
            task_type="USER_EXPLOITATION",
            out_dir="/tmp/test",
            use_firewall=True,
        )
        assert config.use_firewall is True

    def test_agent_fn_args_firewall_env_default(self):
        """Test that firewall_env defaults to None."""
        from cybergym.evaluation.types import AgentFnArguments

        args = AgentFnArguments(
            task_description="test",
            runtime_dir_in_container="/data",
            agent_timeout_seconds=60,
            out_dir="/tmp/test",
        )
        assert args.firewall_env is None

    def test_agent_fn_args_firewall_env_set(self):
        """Test setting firewall_env on AgentFnArguments."""
        from cybergym.evaluation.types import AgentFnArguments

        firewall_env = {
            "HTTP_PROXY": "http://proxy:3128",
            "HTTPS_PROXY": "http://proxy:3128",
        }
        args = AgentFnArguments(
            task_description="test",
            runtime_dir_in_container="/data",
            agent_timeout_seconds=60,
            out_dir="/tmp/test",
            firewall_env=firewall_env,
        )
        assert args.firewall_env == firewall_env


class TestServerConfigNetwork:
    """Tests for the network field in ServerConfig."""

    def test_network_default_none(self):
        """Test that network defaults to None."""
        from cybergym.server.types import ServerConfig

        config = ServerConfig()
        assert config.network is None

    def test_network_custom_value(self):
        """Test setting a custom network name."""
        from cybergym.server.types import ServerConfig

        config = ServerConfig(network="cybergym-internal")
        assert config.network == "cybergym-internal"
