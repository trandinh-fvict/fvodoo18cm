# -*- coding: utf-8 -*-
{
    "name": "Mail RealtimeKit Integration",
    "version": "1.0",
    "summary": "Integrate Cloudflare RealtimeKit with Discuss calls",
    "category": "Discuss",
    "author": "Odoo Community",
    "license": "LGPL-3",
    "depends": ["mail"],
    "data": [
        "views/res_config_settings_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mail_realtimekit/static/src/discuss/call/common/realtimekit_patch.js",
        ],
        "mail_realtimekit.assets_realtimekit": [
            "mail_realtimekit/static/src/discuss/call/common/realtimekit_client.js",
        ],
    },
}
