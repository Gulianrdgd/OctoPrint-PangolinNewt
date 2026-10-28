$(function () {
    "use strict";

    function PangolinViewModel(parameters) {
        var self = this;

        self.settings = parameters[0];

        /* ---- observables ---- */
        self.status      = ko.observable("stopped");
        self.isInstalled = ko.observable(false);
        self.logLines    = ko.observableArray([]);

        self.isRunning = ko.computed(function () {
            return self.status() === "running";
        });

        self.isConfigured = ko.computed(function () {
            try {
                var id     = self.settings.settings.plugins.pangolin.newt_id();
                var secret = self.settings.settings.plugins.pangolin.newt_secret();
                return id && id.trim() !== "" && secret && secret.trim() !== "";
            } catch (e) { return false; }
        });

        self.dotClass = ko.computed(function () {
            var s = self.status();
            if (s === "running")    return "pangolin-dot pangolin-dot--running";
            if (s === "error")      return "pangolin-dot pangolin-dot--error";
            if (s === "installing") return "pangolin-dot pangolin-dot--installing";
            return "pangolin-dot pangolin-dot--stopped";
        });

        self.statusLabel = ko.computed(function () {
            switch (self.status()) {
                case "running":    return "Connected";
                case "error":      return "Error";
                case "installing": return "Installing…";
                default:           return "Stopped";
            }
        });

        /* ---- API helpers ---- */

        function apiCall(cmd, callback) {
            $.ajax({
                url: API_BASEURL + "plugin/pangolin",
                type: "POST",
                dataType: "json",
                contentType: "application/json; charset=UTF-8",
                data: JSON.stringify({ command: cmd }),
                success: function (resp) {
                    if (resp.status    !== undefined) self.status(resp.status);
                    if (resp.installed !== undefined) self.isInstalled(resp.installed);
                    if (resp.log       !== undefined) self.logLines(resp.log);
                    if (callback) callback(resp);
                },
                error: function (xhr) {
                    console.error("Pangolin plugin API error:", xhr.responseText);
                }
            });
        }

        self.refreshStatus = function () { apiCall("status", null); };

        self.startNewt   = function () { apiCall("start",   function () { _pollUntilStable(); }); };
        self.stopNewt    = function () { apiCall("stop",    null); };
        self.restartNewt = function () { apiCall("restart", function () { _pollUntilStable(); }); };
        self.installNewt = function () {
            self.logLines([]);
            apiCall("install", function () { _pollUntilStable(20); });
        };

        /* Poll a few times after a state-changing command so the log updates live */
        function _pollUntilStable(times) {
            var remaining = times || 6;
            var interval = setInterval(function () {
                apiCall("status", null);
                remaining--;
                if (remaining <= 0) clearInterval(interval);
            }, 1500);
        }

        /* ---- lifecycle ---- */

        self.onStartupComplete = function () {
            self.refreshStatus();
            // Refresh every 10 seconds
            setInterval(self.refreshStatus, 10000);
        };
    }

    OCTOPRINT_VIEWMODELS.push([
        PangolinViewModel,
        ["settingsViewModel"],
        ["#sidebar_plugin_pangolin", "#settings_plugin_pangolin"]
    ]);
});
