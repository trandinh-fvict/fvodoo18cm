# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

import requests

from odoo import _, models
from odoo.exceptions import UserError
from odoo.tools import misc

_logger = logging.getLogger(__name__)


class MailIceServerRealtimeKit(models.Model):
    _inherit = "mail.ice.server"

    def _get_realtimekit_ice_servers(self):
        config = self.env["ir.config_parameter"].sudo()
        if not misc.str2bool(config.get_param("mail_realtimekit.enabled", "False")):
            return None
        account_id = config.get_param("mail_realtimekit.account_id")
        api_token = config.get_param("mail_realtimekit.api_token")
        app_id = config.get_param("mail_realtimekit.app_id")
        base_url = config.get_param("mail_realtimekit.api_base_url") or "https://api.cloudflare.com/client/v4"
        endpoint_tpl = config.get_param("mail_realtimekit.turn_endpoint")
        if not endpoint_tpl:
            if not account_id:
                _logger.warning("RealtimeKit TURN endpoint is not configured")
                return None
            template = "{base}/accounts/{account_id}/calls"
            if app_id:
                template += "/apps/{app_id}"
            endpoint_tpl = template + "/sessions/turn"
        endpoint = endpoint_tpl.format(base=base_url, account_id=account_id or "", app_id=app_id or "")
        headers = {"Authorization": f"Bearer {api_token}" if api_token else ""}
        headers = {k: v for k, v in headers.items() if v}
        headers.setdefault("Content-Type", "application/json")
        payload = {}
        ttl = config.get_param("mail_realtimekit.turn_ttl")
        if ttl:
            try:
                payload["ttl"] = int(ttl)
            except ValueError:
                _logger.warning("Invalid RealtimeKit TURN TTL '%s'", ttl)
        payload_param = config.get_param("mail_realtimekit.turn_payload")
        if payload_param:
            try:
                payload.update(json.loads(payload_param))
            except json.JSONDecodeError as error:
                _logger.warning("Invalid JSON payload for RealtimeKit TURN request: %s", error)
        try:
            response = requests.post(endpoint, headers=headers, json=payload or None, timeout=10)
        except requests.RequestException as error:
            _logger.warning("Failed to obtain TURN credentials from Cloudflare RealtimeKit: %s", error)
            return None
        if response.status_code == 401:
            raise UserError(_("Cloudflare RealtimeKit credentials are invalid."))
        if not response.ok:
            _logger.warning(
                "RealtimeKit TURN endpoint returned %(status)s: %(content)s",
                {"status": response.status_code, "content": response.text},
            )
            return None
        try:
            data = response.json()
        except ValueError:
            _logger.warning("RealtimeKit TURN endpoint returned invalid JSON: %s", response.text)
            return None
        result = data.get("result") if isinstance(data, dict) else None
        ice_servers = None
        if isinstance(result, dict):
            ice_servers = result.get("iceServers") or result.get("ice_servers")
        if ice_servers is None and isinstance(data, dict):
            ice_servers = data.get("iceServers") or data.get("ice_servers")
        if not ice_servers:
            _logger.warning("RealtimeKit TURN endpoint did not return any ICE server: %s", data)
            return None
        return ice_servers

    def _get_ice_servers(self):
        realtimekit_servers = self._get_realtimekit_ice_servers()
        if realtimekit_servers:
            return realtimekit_servers
        return super()._get_ice_servers()
