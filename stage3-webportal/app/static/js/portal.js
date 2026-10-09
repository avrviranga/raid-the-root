/*
 * VAULT-03 portal — client bundle
 * Nexora Bank, Internal Systems
 * build 1.4 / 2026-08-02
 */

(function () {
  "use strict";

  var PORTAL = "VAULT-03";

  function readSession() {
    var m = document.cookie.match(/nxb_session=([^;]+)/);
    if (!m) { return null; }
    try {
      return JSON.parse(atob(m[1]));
    } catch (e) {
      return null;
    }
  }

  function refreshDocuments() {
    return fetch("/documents", { credentials: "same-origin" });
  }

  // ------------------------------------------------------------------
  // TODO (NXB-4418): the staging console at /internal is still reachable
  // from this build. IT Infrastructure asked for it to be removed from the
  // client bundle before the portal went live — the call below is commented
  // out but the route itself was never decommissioned on the server.
  //
  // function loadStagingConsole() {
  //   return fetch("/internal", { credentials: "same-origin" })
  //     .then(function (r) { return r.json(); });
  // }
  //
  // Raised with Treasury 2026-07-30. No response.
  // ------------------------------------------------------------------

  function init() {
    var s = readSession();
    if (s) {
      console.log("[" + PORTAL + "] session role:", s.role);
    }
  }

  document.addEventListener("DOMContentLoaded", init);

  window.NexoraPortal = {
    portal: PORTAL,
    refresh: refreshDocuments,
    session: readSession
  };
}());
