/** @odoo-module **/

export const SFU_CLIENT_STATE = {
    DISCONNECTED: "DISCONNECTED",
    CONNECTING: "CONNECTING",
    AUTHENTICATED: "AUTHENTICATED",
    CONNECTED: "CONNECTED",
    CLOSED: "CLOSED",
};

const DEFAULT_TIMEOUT = 10000;

export class RealtimeKitClient extends EventTarget {
    errors = [];

    constructor() {
        super();
        this._state = SFU_CLIENT_STATE.DISCONNECTED;
        this._socket = undefined;
        this._url = undefined;
        this._token = undefined;
        this._options = undefined;
        this._timeout = undefined;
    }

    set state(state) {
        if (state === this._state) {
            return;
        }
        this._state = state;
        this.dispatchEvent(new CustomEvent("stateChange", { detail: { state } }));
    }

    get state() {
        return this._state;
    }

    broadcast(message) {
        this._send({ type: "broadcast", payload: message });
    }

    async connect(url, token, options = {}) {
        this._url = url.replace(/^http/, "ws");
        this._token = token;
        this._options = options;
        this.state = SFU_CLIENT_STATE.CONNECTING;
        return new Promise((resolve, reject) => {
            try {
                this._socket = new WebSocket(this._url);
            } catch (error) {
                this.state = SFU_CLIENT_STATE.CLOSED;
                reject(error);
                return;
            }
            const handleFailure = (error) => {
                clearTimeout(this._timeout);
                if (this.state !== SFU_CLIENT_STATE.CLOSED) {
                    this.state = SFU_CLIENT_STATE.CLOSED;
                }
                reject(error instanceof Event ? new Error("RealtimeKit connection failed") : error);
            };
            this._socket.addEventListener("open", () => {
                clearTimeout(this._timeout);
                this.state = SFU_CLIENT_STATE.AUTHENTICATED;
                this._send({
                    type: "authenticate",
                    token: this._token,
                    sessionId: this._options.channelUUID,
                    clientId: this._options.clientId,
                    metadata: this._options.metadata,
                });
            });
            this._socket.addEventListener("message", (event) => {
                const payload = this._parse(event.data);
                if (!payload) {
                    return;
                }
                switch (payload.type) {
                    case "ready":
                    case "connected":
                        this.state = SFU_CLIENT_STATE.CONNECTED;
                        resolve();
                        return;
                    case "authenticated":
                        this.state = SFU_CLIENT_STATE.AUTHENTICATED;
                        return;
                    case "broadcast":
                    case "connection_change":
                    case "disconnect":
                    case "info_change":
                    case "track":
                        this.dispatchEvent(new CustomEvent("update", { detail: { name: payload.type, payload } }));
                        return;
                    case "error":
                        this.errors.push(payload);
                        handleFailure(new Error(payload.message || "RealtimeKit error"));
                        return;
                }
            });
            this._socket.addEventListener("close", (event) => {
                clearTimeout(this._timeout);
                if (this.state !== SFU_CLIENT_STATE.CLOSED) {
                    this.state = SFU_CLIENT_STATE.CLOSED;
                    this.dispatchEvent(new CustomEvent("stateChange", { detail: { state: this.state, cause: event.code } }));
                }
            });
            this._socket.addEventListener("error", handleFailure);
            this._timeout = setTimeout(() => handleFailure(new Error("RealtimeKit handshake timeout")), DEFAULT_TIMEOUT);
        });
    }

    disconnect() {
        if (this._socket) {
            this._socket.close();
            this._socket = undefined;
        }
        this.state = SFU_CLIENT_STATE.DISCONNECTED;
    }

    async updateUpload(type, track) {
        this._send({ type: "upload", payload: { media: type, active: Boolean(track) } });
    }

    updateDownload(sessionId, states) {
        this._send({ type: "download", payload: { sessionId, states } });
    }

    updateInfo(info, options = {}) {
        this._send({ type: "info", payload: { info, options } });
    }

    _send(message) {
        if (!this._socket || this._socket.readyState !== WebSocket.OPEN) {
            return;
        }
        try {
            this._socket.send(JSON.stringify(message));
        } catch (error) {
            this.errors.push(error);
        }
    }

    _parse(raw) {
        if (!raw) {
            return null;
        }
        try {
            return JSON.parse(raw);
        } catch (error) {
            this.errors.push(error);
            return null;
        }
    }
}
