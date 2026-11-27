"""Dashboard installation (dependency-free)."""

from __future__ import annotations

import asyncio
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ha_stubs  # noqa: E402

ha_stubs.install()

from custom_components.simplex import frontend  # noqa: E402
from custom_components.simplex.frontend import (  # noqa: E402
    CATALOG,
    DASHBOARDS_DIR,
    DashboardInstallError,
    async_install_dashboard,
)


class _Dash:
    def __init__(self, mode="storage"):
        self.mode = mode
        self.saved = None

    async def async_save(self, config):
        self.saved = config


class _Resources:
    def __init__(self, urls):
        self._urls = urls

    def async_items(self):
        return [{"url": u} for u in self._urls]


class _Hass:
    def __init__(self, resources=(), existing=None, ws=True):
        self.dashboards = dict(existing or {})
        self.created = []
        lovelace = type("L", (), {})()
        lovelace.dashboards = self.dashboards
        lovelace.resources = _Resources(resources)
        self.data = {"lovelace": lovelace}
        if ws:
            self.data["websocket_api"] = {"lovelace/dashboards/create": (self._create, None)}

    def _create(self, hass, conn, msg):
        self.created.append(msg)
        self.dashboards[msg["url_path"]] = _Dash()
        conn.send_result(msg["id"], {})

    async def async_add_executor_job(self, fn, *a):
        return fn(*a)


def run(coro):
    return asyncio.run(coro)


class TestBundle(unittest.TestCase):
    def test_every_yaml_is_in_the_catalog_and_loads(self):
        files = {p.stem for p in DASHBOARDS_DIR.glob("*.yaml")}
        self.assertEqual(files, set(CATALOG))
        for name in CATALOG:
            cfg = frontend.load_dashboard(name)
            self.assertTrue(cfg["views"])
            self.assertIn("-", frontend.default_url_path(name))

    def test_card_theme_variables_keep_their_fallback(self):
        """The Messenger themes the cards through --simplex-* variables; every
        use must carry the historical colour as fallback so that the other
        dashboards render exactly as before."""
        import re

        for card in ("simplex-chat-card", "simplex-conversations-card"):
            src = (DASHBOARDS_DIR.parent / "cards" / card / f"{card}.js").read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"var\(--simplex-[\w-]+\)", src), card)

    def test_service_picker_offers_every_dashboard(self):
        import re

        text = (DASHBOARDS_DIR.parent / "services.yaml").read_text(encoding="utf-8")
        block = text.split("install_dashboard:", 1)[1].split("url_path:", 1)[0]
        options = set(re.findall(r"^\s+- (simplex_\w+)\s*$", block, re.M))
        self.assertEqual(options, set(CATALOG))

    def test_navigation_is_rewritten_into_the_dashboard(self):
        cfg = frontend.rewrite_navigation(frontend.load_dashboard("simplex_auto_fr"), "simplex-auto-fr")
        prefixes = [n["navigate_prefix"] for n in frontend._walk(cfg) if isinstance(n, dict) and "navigate_prefix" in n]
        self.assertEqual(prefixes, ["/simplex-auto-fr/simplex-chat"])
        cfg = frontend.rewrite_navigation(frontend.load_dashboard("simplex_android_home_fr"), "my-dash")
        for n in frontend._walk(cfg):
            if isinstance(n, dict) and "navigate_prefix" in n:
                self.assertEqual(n["navigate_prefix"], "/my-dash/simplex-chat")


    def test_messenger_never_navigates_away_from_its_own_view(self):
        """The list card pushes `<prefix>#alias`; if the prefix is not the view that
        hosts the messenger, Home Assistant routes elsewhere and unmounts it."""
        for name in ("simplex_messenger_fr", "simplex_messenger_en"):
            cfg = frontend.rewrite_navigation(frontend.load_dashboard(name), "my-dash")
            views = [v["path"] for v in cfg["views"]]
            self.assertEqual(views, ["messenger"], name)
            cards = [n for n in frontend._walk(cfg) if isinstance(n, dict) and n.get("type") == "custom:simplex-messenger-card"]
            self.assertEqual(len(cards), 1, name)
            prefix = cards[0].get("navigate_prefix")
            # Absent (auto-detected from the URL) or exactly this view.
            self.assertIn(prefix, (None, "/my-dash/messenger"), name)


class TestInstall(unittest.TestCase):
    def test_creates_saves_and_reports_missing_cards(self):
        hass = _Hass()
        res = run(async_install_dashboard(hass, "simplex_auto_fr"))
        self.assertTrue(res["created"])
        self.assertEqual(res["url_path"], "simplex-auto-fr")
        self.assertEqual(hass.created[0]["url_path"], "simplex-auto-fr")
        self.assertTrue(hass.created[0]["allow_single_word"])
        self.assertIsNotNone(hass.dashboards["simplex-auto-fr"].saved)

    def test_existing_dashboard_needs_overwrite(self):
        hass = _Hass(existing={"simplex-auto-fr": _Dash()})
        with self.assertRaises(DashboardInstallError):
            run(async_install_dashboard(hass, "simplex_auto_fr"))
        self.assertIsNone(hass.dashboards["simplex-auto-fr"].saved)
        res = run(async_install_dashboard(hass, "simplex_auto_fr", overwrite=True))
        self.assertFalse(res["created"])
        self.assertIsNotNone(hass.dashboards["simplex-auto-fr"].saved)
        self.assertEqual(hass.created, [])

    def test_yaml_dashboard_is_never_written(self):
        hass = _Hass(existing={"simplex-auto-fr": _Dash(mode="yaml")})
        with self.assertRaises(DashboardInstallError):
            run(async_install_dashboard(hass, "simplex_auto_fr", overwrite=True))

    def test_bad_inputs_and_missing_api(self):
        with self.assertRaises(DashboardInstallError):
            run(async_install_dashboard(_Hass(), "nope"))
        with self.assertRaises(DashboardInstallError):
            run(async_install_dashboard(_Hass(), "simplex_fr", url_path="simplex"))
        with self.assertRaises(DashboardInstallError):
            run(async_install_dashboard(_Hass(ws=False), "simplex_fr"))


class TestCards(unittest.TestCase):
    def test_bundle_is_complete_and_guarded(self):
        files = frontend.card_files()
        self.assertEqual(
            files,
            ["simplex-card-editor.js"]
            + [f"simplex-{n}-card/simplex-{n}-card.js" for n in ("chat", "conversations", "intercom", "messenger")],
        )
        for f in files:
            src = (frontend.CARDS_DIR / f).read_text(encoding="utf-8")
            # The messenger is a minified build: only the guard itself is stable.
            self.assertRegex(src, r"customElements\.get\(", "must tolerate a manual /local copy")
            if f.endswith("-card.js"):
                kind = f.split("/")[0].split("-")[1]
                self.assertIn(f'"simplex-{kind}-card-editor"', src, "card must expose its visual editor")
                self.assertRegex(src, r"getStubConfig", "card must provide a stub config")

    def test_registration_serves_and_loads_each_card_once(self):
        import types

        extra, static = [], []
        sys.modules["homeassistant.components.frontend"] = types.SimpleNamespace(
            add_extra_js_url=lambda hass, url: extra.append(url)
        )
        sys.modules["homeassistant.components.http"].StaticPathConfig = (
            lambda url, path, cache: (url, path, cache)
        )

        async def reg(paths):
            static.extend(paths)

        hass = type("H", (), {})()
        hass.http = types.SimpleNamespace(async_register_static_paths=reg)
        data: dict = {}
        urls = run(frontend.async_register_cards(hass, data))
        self.assertEqual(len(urls), 5)
        self.assertEqual(extra, urls)
        self.assertTrue(all(u.startswith("/simplex_cards/") and "?v=" in u for u in urls))
        self.assertEqual(static[0][0], "/simplex_cards")
        self.assertEqual(run(frontend.async_register_cards(hass, data)), [], "idempotent")
        self.assertEqual(len(extra), 5)


if __name__ == "__main__":
    unittest.main()
