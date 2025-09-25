# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    mail_realtimekit_enabled = fields.Boolean(string="Use Cloudflare RealtimeKit", config_parameter="mail_realtimekit.enabled")
    mail_realtimekit_account_id = fields.Char(string="Cloudflare account ID", config_parameter="mail_realtimekit.account_id")
    mail_realtimekit_app_id = fields.Char(string="RealtimeKit application ID", config_parameter="mail_realtimekit.app_id")
    mail_realtimekit_api_token = fields.Char(string="RealtimeKit API token", config_parameter="mail_realtimekit.api_token")
    mail_realtimekit_api_base_url = fields.Char(
        string="RealtimeKit API base URL", default="https://api.cloudflare.com/client/v4",
        config_parameter="mail_realtimekit.api_base_url",
    )
    mail_realtimekit_session_endpoint = fields.Char(
        string="Session endpoint template", config_parameter="mail_realtimekit.session_endpoint",
        help="Template used to provision a RealtimeKit session. The placeholders {base}, {account_id} and {app_id} are replaced automatically.",
    )
    mail_realtimekit_session_payload = fields.Text(
        string="Session payload", config_parameter="mail_realtimekit.session_payload",
        help="Optional JSON payload merged with the default session request.",
    )
    mail_realtimekit_client_endpoint = fields.Char(
        string="Client endpoint template", config_parameter="mail_realtimekit.client_endpoint",
        help="Template used to request client tokens. Supports {base}, {account_id}, {app_id} and {session_id} placeholders.",
    )
    mail_realtimekit_client_payload = fields.Text(
        string="Client payload", config_parameter="mail_realtimekit.client_payload",
        help="Optional JSON payload merged with the default client request.",
    )
    mail_realtimekit_turn_endpoint = fields.Char(
        string="TURN endpoint template", config_parameter="mail_realtimekit.turn_endpoint",
        help="Template used to request TURN credentials. Supports {base}, {account_id} and {app_id} placeholders.",
    )
    mail_realtimekit_turn_payload = fields.Text(
        string="TURN payload", config_parameter="mail_realtimekit.turn_payload",
        help="Optional JSON payload appended to the TURN request.",
    )
    mail_realtimekit_turn_ttl = fields.Char(
        string="TURN TTL", config_parameter="mail_realtimekit.turn_ttl",
        help="Optional TTL passed to the TURN credential endpoint.",
    )
    mail_realtimekit_client_disconnect_endpoint = fields.Char(
        string="Disconnect endpoint template", config_parameter="mail_realtimekit.client_disconnect_endpoint",
        help="Endpoint used to disconnect clients. Supports {base}, {account_id}, {app_id}, {session_id} and {client_id} placeholders.",
    )
