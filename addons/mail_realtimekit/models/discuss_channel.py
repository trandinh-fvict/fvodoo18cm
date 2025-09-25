# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class DiscussChannel(models.Model):
    _inherit = "discuss.channel"

    realtimekit_session_token = fields.Char(groups="base.group_system")
    realtimekit_session_expiration = fields.Datetime(groups="base.group_system")
    realtimekit_session_metadata = fields.Text(groups="base.group_system")

    def _clear_realtimekit_session(self):
        self.write(
            {
                "realtimekit_session_token": False,
                "realtimekit_session_expiration": False,
                "realtimekit_session_metadata": False,
                "sfu_channel_uuid": False,
                "sfu_server_url": False,
            }
        )

    def _is_realtimekit_session_valid(self):
        self.ensure_one()
        if not self.sfu_channel_uuid or not self.sfu_server_url or not self.realtimekit_session_token:
            return False
        if self.realtimekit_session_expiration and self.realtimekit_session_expiration <= fields.Datetime.now():
            return False
        return True
