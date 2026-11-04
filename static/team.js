/* Hockey Network USA: "choose your team". The choice lives only in this
   browser (localStorage); with storage blocked it falls back to Utah. */
(function () {
  var KEY = "hnusa-team", DEFAULT = "UTA", team = DEFAULT, L = null;
  try { team = localStorage.getItem(KEY) || DEFAULT; } catch (e) {}
  var chosen = (function () { try { return !!localStorage.getItem(KEY); } catch (e) { return false; } })();
  var dlg = document.getElementById("teampick");

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function badge(ab) {
    var b = dlg && dlg.querySelector('button[data-team="' + ab + '"] .badge');
    return b ? b.outerHTML : '<span class="badge">' + esc(ab) + "</span>";
  }
  function name(ab) { return (L && L.teams[ab] && L.teams[ab].name) || ab; }
  function ord(n) { n = +n; var s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function day(iso) { var d = new Date(iso + "T12:00:00"); return d.toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"}); }
  function when(g) {
    if (!g.start) return day(g.date);
    var d = new Date(g.start);
    return d.toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"}) + " · " +
      d.toLocaleTimeString(undefined, {hour: "numeric", minute: "2-digit"});
  }

  function renderPanel() {
    var el = document.getElementById("myteam");
    if (!el || !L) return;
    var t = L.teams[team];
    if (!t) { el.innerHTML = ""; return; }
    var mine = L.finals.filter(function (g) { return g.away === team || g.home === team; });
    var next = L.upcoming.filter(function (g) { return g.away === team || g.home === team; }).slice(0, 3);
    var h = '<div class="mt-head">' + badge(team) + "<div><span class=kicker>Your team</span><h2>" + esc(t.name) + "</h2>" +
      '<p class="meta">' + t.w + "-" + t.l + "-" + t.otl + " · " + t.pts + " pts · " + ord(t.div_rank) + " in the " + esc(t.division) +
      " · Last 10: " + esc(t.l10) + "</p></div>" +
      '<button type="button" class="btn ghost" data-open-picker>' + (chosen ? "Change team" : "Not your team? Pick yours") + "</button></div>";
    if (mine.length) {
      var g = mine[0], us = g.away === team, a = us ? g.as : g.hs, b = us ? g.hs : g.as;
      var res = a > b ? "W" : (g.ending === "OT" || g.ending === "SO") ? "OTL" : "L";
      h += '<div class="mt-last"><span class="kicker">Last game · ' + day(g.date) + "</span><p class=score>" +
        '<b class="r-' + res + '">' + res + " " + a + "-" + b + (g.ending !== "REG" ? " (" + g.ending + ")" : "") + "</b> " +
        (us ? "at " : "vs ") + esc(name(us ? g.home : g.away)) + "</p><div class=vids>" +
        (g.recap ? '<a class="vid" target="_blank" rel="noopener" href="' + esc(g.recap) + '">&#9654; Watch the recap</a>' : "") +
        (g.condensed ? '<a class="vid" target="_blank" rel="noopener" href="' + esc(g.condensed) + '">&#9654; Condensed game</a>' : "") +
        "</div>";
      var goals = g.goals.filter(function (x) { return x.team === team && x.clip; });
      if (goals.length) {
        h += '<ul class="goals">' + goals.map(function (x) {
          return '<li><a target="_blank" rel="noopener" href="' + esc(x.clip) + '">&#9654; ' + esc(x.scorer) + "</a>" +
            '<span class="meta"> ' + esc(x.time) + (x.strength === "pp" ? " · PP" : x.strength === "sh" ? " · SH" : "") + "</span></li>";
        }).join("") + "</ul>";
      }
      h += "</div>";
      if (mine.length > 1) {
        h += '<div class="mt-list"><span class="kicker">This week</span><ul>' + mine.slice(1, 5).map(function (g) {
          var us = g.away === team, a = us ? g.as : g.hs, b = us ? g.hs : g.as;
          var r = a > b ? "W" : (g.ending === "OT" || g.ending === "SO") ? "OTL" : "L";
          return "<li>" + day(g.date) + ' <b class="r-' + r + '">' + r + " " + a + "-" + b + "</b> " + (us ? "at " : "vs ") +
            esc(name(us ? g.home : g.away)) + (g.recap ? ' <a target="_blank" rel="noopener" href="' + esc(g.recap) + '">recap</a>' : "") + "</li>";
        }).join("") + "</ul></div>";
      }
    }
    if (next.length) {
      h += '<div class="mt-list"><span class="kicker">Coming up</span><ul>' + next.map(function (g) {
        return "<li>" + when(g) + " · " + (g.away === team ? "at " + esc(name(g.home)) : "vs " + esc(name(g.away))) + "</li>";
      }).join("") + "</ul></div>";
    }
    h += '<p class="mt-foot"><a href="/highlights/">All of this week\'s highlights &rarr;</a>' +
      (team === "UTA" ? ' · <a href="/mammoth/">Mammoth page</a>' : "") + "</p>";
    el.innerHTML = h;
    el.querySelectorAll("[data-open-picker]").forEach(function (b) { b.onclick = open; });
  }

  function filterHighlights() {
    var box = document.getElementById("onlymine");
    if (!box) return;
    var only = box.checked;
    document.querySelectorAll(".game").forEach(function (g) {
      var on = g.getAttribute("data-teams").split(" ").indexOf(team) >= 0;
      g.classList.toggle("is-mine", on);
      g.hidden = only && !on;
      if (on) g.parentNode.prepend(g);
    });
  }

  function apply() {
    document.querySelectorAll("[data-myteam-label]").forEach(function (e) { e.textContent = team; });
    document.querySelectorAll("[data-myteam-name]").forEach(function (e) { e.textContent = name(team); });
    if (dlg) dlg.querySelectorAll("button[data-team]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-team") === team); });
    renderPanel();
    filterHighlights();
  }

  function open() { if (dlg && dlg.showModal) dlg.showModal(); }
  document.querySelectorAll("[data-open-picker]").forEach(function (b) { b.onclick = open; });
  if (dlg) dlg.querySelectorAll("button[data-team]").forEach(function (b) {
    b.onclick = function () {
      team = b.getAttribute("data-team"); chosen = true;
      try { localStorage.setItem(KEY, team); } catch (e) {}
      dlg.close(); apply();
    };
  });
  var box = document.getElementById("onlymine");
  if (box) box.onchange = filterHighlights;

  apply();
  fetch("/data/league.json").then(function (r) { return r.json(); }).then(function (d) { L = d; apply(); }).catch(function () {});
})();
