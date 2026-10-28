$(function () {
    "use strict";

    var PLUGIN = "pangolin_newt";
    var MAX_LOG = 200;

    function PangolinNewtViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0];
        self.loginState = parameters[1];

        /* ---- state pushed by the backend ---- */
        self.state            = ko.observable("stopped");
        self.message          = ko.observable("");
        self.configured       = ko.observable(false);
        self.secretSet        = ko.observable(false);
        self.arch             = ko.observable("");
        self.pinnedVersion    = ko.observable("");
        self.installedVersion = ko.observable("");
        self.logLines         = ko.observableArray([]);

        /* ---- UI state ---- */
        self.busy        = ko.observable(false);
        self.actionError = ko.observable("");
        self.settings    = undefined; // set in onBeforeBinding
        var lastLine = 0;

        self.isActive = ko.pureComputed(function () {
            var s = self.state();
            return s === "connecting" || s === "connected";
        });
        self.canStart = ko.pureComputed(function () {
            return !self.busy() && self.configured() && !self.isActive() && self.state() !== "installing";
        });
        self.canStop = ko.pureComputed(function () {
            return !self.busy() && self.isActive();
        });
        self.canRestart = ko.pureComputed(function () {
            return !self.busy() && self.configured() && self.state() !== "installing";
        });
        self.canReinstall = ko.pureComputed(function () {
            return !self.busy() && self.state() !== "installing";
        });

        self.statusLabel = ko.pureComputed(function () {
            switch (self.state()) {
                case "connected":     return "Connected";
                case "connecting":    return "Connecting…";
                case "installing":    return "Installing Newt…";
                case "not_installed": return "Newt not installed";
                case "error":         return "Error";
                default:              return self.configured() ? "Stopped" : "Not configured";
            }
        });
        self.dotClass = ko.pureComputed(function () {
            var s = self.state();
            if (s === "stopped" && !self.configured()) s = "not_installed";
            return "pangolin-dot pangolin-dot--" + s;
        });
        self.versionLabel = ko.pureComputed(function () {
            var pinned = self.pinnedVersion();
            var installed = self.installedVersion();
            if (!installed) return pinned + " (not installed)";
            return installed.indexOf(pinned) !== -1 ? installed : installed + " (update to " + pinned + " pending)";
        });

        /* ---- applying backend state ---- */

        function logElement() {
            return $("#sidebar_plugin_pangolin_newt .pangolin-log")[0];
        }

        self.applyState = function (data, replaceLog) {
            if (!data) return;
            if (replaceLog || data.last_line < lastLine) {
                // Full snapshot, or the server restarted and numbering began again
                self.logLines([]);
                lastLine = 0;
            }

            if (data.state !== undefined)             self.state(data.state);
            if (data.message !== undefined)           self.message(data.message);
            if (data.configured !== undefined)        self.configured(data.configured);
            if (data.secret_set !== undefined)        self.secretSet(data.secret_set);
            if (data.arch !== undefined)              self.arch(data.arch);
            if (data.pinned_version !== undefined)    self.pinnedVersion(data.pinned_version);
            if (data.installed_version !== undefined) self.installedVersion(data.installed_version || "");

            var fresh = [];
            _.each(data.log || [], function (entry) {
                if (entry.n > lastLine) {
                    fresh.push(entry.line);
                    lastLine = entry.n;
                }
            });
            if (!fresh.length) return;

            var el = logElement();
            var atBottom = !el || el.scrollHeight - el.scrollTop - el.clientHeight < 20;
            var lines = self.logLines().concat(fresh);
            self.logLines(lines.slice(-MAX_LOG));
            if (el && atBottom) el.scrollTop = el.scrollHeight;
        };

        self.refresh = function () {
            if (!self.loginState.isAdmin()) return;
            OctoPrint.simpleApiGet(PLUGIN).done(function (data) {
                self.applyState(data, true);
            });
        };

        function command(cmd) {
            self.busy(true);
            self.actionError("");
            return OctoPrint.simpleApiCommand(PLUGIN, cmd, {})
                .done(function (resp) {
                    self.applyState(resp);
                    if (!resp.ok) self.actionError(resp.msg);
                })
                .fail(function (xhr) {
                    self.actionError("Request failed (" + xhr.status + ").");
                })
                .always(function () {
                    self.busy(false);
                });
        }

        self.startNewt     = function () { command("start"); };
        self.stopNewt      = function () { command("stop"); };
        self.restartNewt   = function () { command("restart"); };
        self.reinstallNewt = function () { command("reinstall"); };

        self.openSettings = function () {
            self.settingsViewModel.show("#settings_plugin_" + PLUGIN);
        };

        /* ---- settings validation ---- */

        function trimmed(observable) {
            return ((observable && observable()) || "").trim();
        }

        self.endpointError = ko.pureComputed(function () {
            if (!self.settings) return "";
            return /^https?:\/\/[^\s\/]+/i.test(trimmed(self.settings.pangolin_endpoint))
                ? "" : "Enter a full URL, for example https://app.pangolin.net. Invalid URLs are not saved.";
        });
        self.endpointWarning = ko.pureComputed(function () {
            if (!self.settings || self.endpointError()) return "";
            return /^http:\/\//i.test(trimmed(self.settings.pangolin_endpoint))
                ? "Plain http sends your credentials unencrypted. Use https if you can." : "";
        });
        self.idError = ko.pureComputed(function () {
            if (!self.settings) return "";
            var id = trimmed(self.settings.newt_id);
            if (!id) return "Required.";
            return /\s/.test(id) ? "The ID cannot contain spaces." : "";
        });
        self.secretError = ko.pureComputed(function () {
            if (!self.settings) return "";
            var secret = trimmed(self.settings.newt_secret);
            if (!secret) return self.secretSet() ? "" : "Required.";
            return /\s/.test(secret) ? "The secret cannot contain spaces." : "";
        });
        self.secretPlaceholder = ko.pureComputed(function () {
            return self.secretSet() ? "Secret saved. Type to replace it." : "Paste your Newt secret";
        });

        /* ---- lifecycle ---- */

        self.onBeforeBinding = function () {
            self.settings = self.settingsViewModel.settings.plugins[PLUGIN];
        };

        self.onDataUpdaterPluginMessage = function (plugin, data) {
            if (plugin !== PLUGIN) return;
            self.applyState(data);
        };

        self.onStartupComplete = self.refresh;
        self.onUserLoggedIn    = self.refresh;
        self.onSettingsShown   = self.refresh;
        self.onServerReconnect = self.refresh;
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: PangolinNewtViewModel,
        dependencies: ["settingsViewModel", "loginStateViewModel"],
        elements: ["#sidebar_plugin_pangolin_newt", "#settings_plugin_pangolin_newt"]
    });
});
