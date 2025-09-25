/** @odoo-module **/

import { RtcService, CONNECTION_TYPES } from "@mail/discuss/call/common/rtc_service";
import { memoize } from "@web/core/utils/functions";
import { loadBundle } from "@web/core/assets";
import { patch } from "@web/core/utils/patch";
import { browser } from "@web/core/browser/browser";

const loadRealtimeKitAssets = memoize(async () => {
    await loadBundle("mail_realtimekit.assets_realtimekit");
    return odoo.loader.modules.get("@mail_realtimekit/discuss/call/common/realtimekit_client");
});

patch(RtcService.prototype, "mail_realtimekit.load_sfu", {
    async _loadSfu(...args) {
        if (this.serverInfo?.provider === "cloudflare") {
            const load = async () => {
                const module = await loadRealtimeKitAssets();
                this.SFU_CLIENT_STATE = module.SFU_CLIENT_STATE;
                this.sfuClient = new module.RealtimeKitClient();
            };
            try {
                await load();
            } catch (error) {
                await new Promise((resolve, reject) => {
                    setTimeout(async () => {
                        try {
                            await load();
                        } catch (retryError) {
                            reject(retryError);
                            return;
                        }
                        resolve();
                    }, 1000);
                });
            }
            return;
        }
        return this._super(...args);
    },
});

patch(RtcService.prototype, "mail_realtimekit.call", {
    async call({ asFallback = false } = {}) {
        if (this.serverInfo?.provider !== "cloudflare") {
            return this._super({ asFallback });
        }
        if (asFallback && !this.state.fallbackMode) {
            return;
        }
        if (this.state.connectionType === CONNECTION_TYPES.SERVER) {
            if (this.sfuClient.state === this.SFU_CLIENT_STATE.DISCONNECTED) {
                browser.clearTimeout(this.sfuTimeout);
                this.sfuTimeout = browser.setTimeout(() => {
                    this.log(this.selfSession, "sfu connection timeout", { important: true });
                    this._downgradeConnection();
                }, 10000);
                await this.sfuClient.connect(this.serverInfo.url, this.serverInfo.jsonWebToken, {
                    channelUUID: this.serverInfo.channelUUID,
                    clientId: this.serverInfo.clientId,
                    metadata: this.serverInfo.metadata,
                    iceServers: this.serverInfo.iceServers || this.iceServers,
                });
            }
            return;
        }
        if (this.state.channel.rtcSessions.length === 0) {
            return;
        }
        return this._super({ asFallback });
    },
});
