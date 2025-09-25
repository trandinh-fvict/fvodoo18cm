# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

import requests

from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.tools import misc

_logger = logging.getLogger(__name__)


class DiscussChannelRtcSession(models.Model):
    _inherit = "discuss.channel.rtc.session"

    realtimekit_client_token = fields.Char(groups="base.group_system")
    realtimekit_client_id = fields.Char(groups="base.group_system")
    realtimekit_token_expiration = fields.Datetime(groups="base.group_system")

    def _clear_realtimekit_credentials(self):
        self.write(
            {
                "realtimekit_client_token": False,
                "realtimekit_client_id": False,
                "realtimekit_token_expiration": False,
            }
        )

    def _ensure_realtimekit_credentials(self):
        config = self.env["ir.config_parameter"].sudo()
        if not misc.str2bool(config.get_param("mail_realtimekit.enabled", "False")):
            return None
        self.ensure_one()
        if not self.channel_id or not self.channel_id._is_realtimekit_session_valid():
            return None
        if (
            self.realtimekit_client_token
            and (not self.realtimekit_token_expiration or self.realtimekit_token_expiration > fields.Datetime.now())
        ):
            return {
                "token": self.realtimekit_client_token,
                "client_id": self.realtimekit_client_id,
                "expires_at": self.realtimekit_token_expiration,
            }
        credentials = self._request_realtimekit_client_token(config)
        if credentials:
            self.write(
                {
                    "realtimekit_client_token": credentials.get("token"),
                    "realtimekit_client_id": credentials.get("client_id"),
                    "realtimekit_token_expiration": credentials.get("expires_at"),
                }
            )
            return credentials
        return None

    def _request_realtimekit_client_token(self, config):
        account_id = config.get_param("mail_realtimekit.account_id")
        api_token = config.get_param("mail_realtimekit.api_token")
        app_id = config.get_param("mail_realtimekit.app_id")
        base_url = config.get_param("mail_realtimekit.api_base_url") or "https://api.cloudflare.com/client/v4"
        endpoint_tpl = config.get_param("mail_realtimekit.client_endpoint")
        if not endpoint_tpl:
            if not account_id or not app_id:
                _logger.warning("RealtimeKit client endpoint is not configured")
                return None
            endpoint_tpl = (
                "{base}/accounts/{account_id}/calls/apps/{app_id}/sessions/{session_id}/clients"
            )
        endpoint = endpoint_tpl.format(
            base=base_url,
            account_id=account_id or "",
            app_id=app_id or "",
            session_id=self.channel_id.sfu_channel_uuid or "",
        )
        payload = {
            "sessionId": self.channel_id.sfu_channel_uuid,
            "metadata": {
                "odooSessionId": self.id,
                "channelId": self.channel_id.id,
            },
        }
        payload_param = config.get_param("mail_realtimekit.client_payload")
        if payload_param:
            try:
                payload.update(json.loads(payload_param))
            except json.JSONDecodeError as error:
                _logger.warning("Invalid JSON payload for RealtimeKit client request: %s", error)
        headers = {"Authorization": f"Bearer {api_token}" if api_token else ""}
        headers = {k: v for k, v in headers.items() if v}
        headers.setdefault("Content-Type", "application/json")
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        except requests.RequestException as error:
            _logger.warning("Failed to obtain RealtimeKit client token: %s", error)
            return None
        if response.status_code == 401:
            _logger.error("RealtimeKit client endpoint rejected credentials")
            return None
        if not response.ok:
            _logger.warning(
                "RealtimeKit client endpoint returned %(status)s: %(content)s",
                {"status": response.status_code, "content": response.text},
            )
            return None
        try:
            data = response.json()
        except ValueError:
            _logger.warning("RealtimeKit client endpoint returned invalid JSON: %s", response.text)
            return None
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict):
            data = result
        token = data.get("token") or data.get("jwt") or data.get("jsonWebToken")
        if not token:
            _logger.warning("RealtimeKit client token is missing from response: %s", data)
            return None
        expires_at = data.get("expiresAt") or data.get("expires_at")
        expires_in = data.get("expiresIn") or data.get("ttl")
        expiration_dt = None
        if expires_at:
            try:
                expiration_dt = fields.Datetime.to_datetime(expires_at)
            except ValueError:
                _logger.warning("RealtimeKit client expiration is invalid: %s", expires_at)
        elif expires_in:
            try:
                expiration_dt = fields.Datetime.now() + relativedelta(seconds=int(expires_in))
            except (TypeError, ValueError):
                _logger.warning("RealtimeKit client TTL is invalid: %s", expires_in)
        return {
            "token": token,
            "client_id": data.get("clientId") or data.get("client_id"),
            "expires_at": expiration_dt,
        }

    def action_disconnect(self):
        config = self.env["ir.config_parameter"].sudo()
        if misc.str2bool(config.get_param("mail_realtimekit.enabled", "False")):
            self._disconnect_realtimekit_clients(config)
        return super().action_disconnect()

    def _disconnect_realtimekit_clients(self, config):
        account_id = config.get_param("mail_realtimekit.account_id")
        api_token = config.get_param("mail_realtimekit.api_token")
        app_id = config.get_param("mail_realtimekit.app_id")
        base_url = config.get_param("mail_realtimekit.api_base_url") or "https://api.cloudflare.com/client/v4"
        endpoint_tpl = config.get_param("mail_realtimekit.client_disconnect_endpoint")
        if not endpoint_tpl:
            if not account_id or not app_id:
                return
            endpoint_tpl = (
                "{base}/accounts/{account_id}/calls/apps/{app_id}/sessions/{session_id}/clients/{client_id}"
            )
        headers = {"Authorization": f"Bearer {api_token}" if api_token else ""}
        headers = {k: v for k, v in headers.items() if v}
        for session in self:
            if not session.realtimekit_client_id or not session.channel_id.sfu_channel_uuid:
                continue
            endpoint = endpoint_tpl.format(
                base=base_url,
                account_id=account_id or "",
                app_id=app_id or "",
                session_id=session.channel_id.sfu_channel_uuid,
                client_id=session.realtimekit_client_id,
            )
            try:
                response = requests.delete(endpoint, headers=headers, timeout=5)
            except requests.RequestException:
                continue
            if not response.ok and response.status_code not in (404, 410):
                _logger.debug(
                    "RealtimeKit failed to disconnect client %(client)s (%(status)s)",
                    {"client": session.realtimekit_client_id, "status": response.status_code},
                )
            session._clear_realtimekit_credentials()
