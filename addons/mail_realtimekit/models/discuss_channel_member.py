# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
import logging

import requests

from dateutil.relativedelta import relativedelta

from odoo import fields, models
from odoo.tools import misc

from odoo.addons.mail.models.discuss.discuss_channel_member import SFU_MODE_THRESHOLD

_logger = logging.getLogger(__name__)


class DiscussChannelMember(models.Model):
    _inherit = "discuss.channel.member"

    def _join_sfu(self, ice_servers=None):
        config = self.env["ir.config_parameter"].sudo()
        if not misc.str2bool(config.get_param("mail_realtimekit.enabled", "False")):
            return super()._join_sfu(ice_servers)
        for member in self:
            member._join_realtimekit(config, ice_servers)

    def _join_realtimekit(self, config, ice_servers=None):
        if len(self.channel_id.rtc_session_ids) < SFU_MODE_THRESHOLD:
            if self.channel_id.sfu_channel_uuid or self.channel_id.sfu_server_url:
                self.channel_id._clear_realtimekit_session()
                self.channel_id.rtc_session_ids._clear_realtimekit_credentials()
            return
        if self.channel_id._is_realtimekit_session_valid():
            return
        account_id = config.get_param("mail_realtimekit.account_id")
        api_token = config.get_param("mail_realtimekit.api_token")
        app_id = config.get_param("mail_realtimekit.app_id")
        base_url = config.get_param("mail_realtimekit.api_base_url") or "https://api.cloudflare.com/client/v4"
        endpoint_tpl = config.get_param("mail_realtimekit.session_endpoint")
        if not endpoint_tpl:
            if not account_id or not app_id:
                _logger.warning("RealtimeKit session endpoint is not configured")
                return
            endpoint_tpl = "{base}/accounts/{account_id}/calls/apps/{app_id}/sessions"
        endpoint = endpoint_tpl.format(base=base_url, account_id=account_id or "", app_id=app_id or "")
        payload = {
            "metadata": {
                "channelId": self.channel_id.id,
            }
        }
        payload_param = config.get_param("mail_realtimekit.session_payload")
        if payload_param:
            try:
                payload.update(json.loads(payload_param))
            except json.JSONDecodeError as error:
                _logger.warning("Invalid JSON payload for RealtimeKit session request: %s", error)
        headers = {"Authorization": f"Bearer {api_token}" if api_token else ""}
        headers = {k: v for k, v in headers.items() if v}
        headers.setdefault("Content-Type", "application/json")
        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        except requests.RequestException as error:
            _logger.warning("Failed to create RealtimeKit session: %s", error)
            return
        if not response.ok:
            _logger.warning(
                "RealtimeKit session endpoint returned %(status)s: %(content)s",
                {"status": response.status_code, "content": response.text},
            )
            return
        try:
            data = response.json()
        except ValueError:
            _logger.warning("RealtimeKit session endpoint returned invalid JSON: %s", response.text)
            return
        result = data.get("result") if isinstance(data, dict) else None
        if isinstance(result, dict):
            data = result
        session_uuid = data.get("sessionId") or data.get("session_id") or data.get("uuid")
        ws_url = data.get("wsUrl") or data.get("ws_url") or data.get("url")
        token = data.get("token") or data.get("jwt") or data.get("jsonWebToken")
        if not session_uuid or not ws_url or not token:
            _logger.warning("RealtimeKit session response missing data: %s", data)
            return
        expires_at = data.get("expiresAt") or data.get("expires_at")
        expires_in = data.get("expiresIn") or data.get("ttl")
        expiration_dt = None
        if expires_at:
            try:
                expiration_dt = fields.Datetime.to_datetime(expires_at)
            except ValueError:
                _logger.warning("RealtimeKit session expiration is invalid: %s", expires_at)
        elif expires_in:
            try:
                expiration_dt = fields.Datetime.now() + relativedelta(seconds=int(expires_in))
            except (TypeError, ValueError):
                _logger.warning("RealtimeKit session TTL is invalid: %s", expires_in)
        metadata = data.get("metadata") or {}
        self.channel_id.write(
            {
                "sfu_channel_uuid": session_uuid,
                "sfu_server_url": ws_url,
                "realtimekit_session_token": token,
                "realtimekit_session_expiration": expiration_dt,
                "realtimekit_session_metadata": json.dumps(metadata) if metadata else False,
            }
        )
        self.channel_id.rtc_session_ids._clear_realtimekit_credentials()
        for session in self.channel_id.rtc_session_ids:
            session._bus_send(
                "discuss.channel.rtc.session/sfu_hot_swap",
                {"serverInfo": self._get_rtc_server_info(session, ice_servers)},
            )

    def _get_rtc_server_info(self, rtc_session, ice_servers=None, key=None):
        config = self.env["ir.config_parameter"].sudo()
        if not misc.str2bool(config.get_param("mail_realtimekit.enabled", "False")):
            return super()._get_rtc_server_info(rtc_session, ice_servers, key=key)
        if not self.channel_id._is_realtimekit_session_valid():
            self._join_realtimekit(config, ice_servers)
        if not self.channel_id._is_realtimekit_session_valid():
            return None
        credentials = rtc_session._ensure_realtimekit_credentials()
        if not credentials:
            return None
        server_info = {
            "url": self.channel_id.sfu_server_url,
            "channelUUID": self.channel_id.sfu_channel_uuid,
            "jsonWebToken": credentials.get("token"),
            "provider": "cloudflare",
        }
        metadata = self.channel_id.realtimekit_session_metadata
        if metadata:
            try:
                server_info["metadata"] = json.loads(metadata)
            except json.JSONDecodeError:
                server_info["metadata"] = metadata
        if credentials.get("client_id"):
            server_info["clientId"] = credentials.get("client_id")
        return server_info
