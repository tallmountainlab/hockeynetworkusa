/* Hockey Network USA: "choose your team".
   The choice lives only in this browser (localStorage). With no choice the
   site shows the Utah Mammoth in the site's own colors; once a visitor
   picks a team, the whole site takes that team's colors and the home page
   leads with that team. Videos play in YouTube's privacy-enhanced player. */
(function () {
  var KEY = "hnusa-team", DEFAULT = "UTA", team = DEFAULT, chosen = false, L = null, V = [];
  try { var saved = localStorage.getItem(KEY); if (saved) { team = saved; chosen = true; } } catch (e) {}
  var dlg = document.getElementById("teampick");
  var THEMES = window.HNUSA_THEMES || {};

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function badge(ab, big) {
    var b = dlg && dlg.querySelector('button[data-team="' + ab + '"] .badge');
    var h = b ? b.outerHTML : '<span class="badge">' + esc(ab) + "</span>";
    return big ? h.replace('class="badge"', 'class="badge big"') : h;
  }
  function T(ab) { return (L && L.teams[ab]) || null; }
  function name(ab) { var t = T(ab); return t ? t.name : ab; }
  function ord(n) { n = +n; var s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function day(iso) { return new Date(iso + "T12:00:00").toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"}); }
  function when(g) {
    if (!g.start) return day(g.date);
    var d = new Date(g.start);
    return d.toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"}) + " · " +
      d.toLocaleTimeString(undefined, {hour: "numeric", minute: "2-digit"});
  }
  function views(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + "M views" : n >= 1e3 ? Math.round(n / 1e3) + "K views" : n + " views"; }
  function result(g, ab) {
    var us = g.away === ab, a = us ? g.as : g.hs, b = us ? g.hs : g.as;
    return {us: us, a: a, b: b, r: a > b ? "W" : (g.ending === "OT" || g.ending === "SO") ? "OTL" : "L",
            opp: us ? g.home : g.away};
  }
  function ytCard(v, cls) {
    return '<button type="button" class="yt ' + (cls || "") + '" data-yt="' + esc(v.id) + '" aria-label="Play ' + esc(v.title) + '">' +
      '<img src="' + esc(v.thumb) + '" alt="" loading="lazy"><span class="play"></span></button>';
  }
  function teamVideos(ab) { return V.filter(function (v) { return v.teams && v.teams.indexOf(ab) >= 0; }); }

  /* ---------- theme ---------- */
  function paint() {
    var r = document.documentElement, c = chosen && THEMES[team];
    ["--navy", "--goal", "--ice"].forEach(function (k) { r.style.removeProperty(k); });
    if (c) {
      r.dataset.team = team;
      r.style.setProperty("--navy", c.navy); r.style.setProperty("--goal", c.goal); r.style.setProperty("--ice", c.ice);
    } else { delete r.dataset.team; }
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute("content", c ? c.navy : "#0b1d33");
  }

  /* ---------- hero ---------- */
  var heroText = document.getElementById("herotext"), heroNext = document.getElementById("heronext");
  var heroDefault = heroText && heroText.innerHTML, nextDefault = heroNext && heroNext.innerHTML;
  function renderHero() {
    if (!heroText || !L) return;
    if (!chosen || team === "UTA" && !chosen) { heroText.innerHTML = heroDefault; heroNext.innerHTML = nextDefault; return; }
    var t = T(team); if (!t) return;
    heroText.innerHTML = '<p class="kicker">Your team</p><h1>' + esc(t.name) + "</h1><p>" + t.w + "-" + t.l + "-" + t.otl +
      ", " + t.pts + " points, " + ord(t.div_rank) + " in the " + esc(t.division) + " Division. Scores, goals and highlights " +
      "below, plus the best of the rest of the league on the side.</p>";
    var n = L.upcoming.filter(function (g) { return g.away === team || g.home === team; })[0];
    heroNext.innerHTML = n ? '<div class="nextgame"><span class="kicker">Next game</span><strong>' +
      (n.away === team ? "at " + esc(name(n.home)) : "vs " + esc(name(n.away))) + "</strong><span>" + when(n) +
      (n.venue ? " · " + esc(n.venue) : "") + '</span><a href="/highlights/">Scores &amp; highlights &rarr;</a></div>' : "";
  }

  /* ---------- team zone ---------- */
  function renderZone() {
    var el = document.getElementById("myteam");
    if (!el || !L) return;
    var t = T(team);
    if (!t) { el.innerHTML = ""; return; }
    var mine = L.finals.filter(function (g) { return g.away === team || g.home === team; });
    var next = L.upcoming.filter(function (g) { return g.away === team || g.home === team; }).slice(0, 4);
    var vids = teamVideos(team);
    var h = '<div class="mt-head">' + badge(team, true) + "<div><span class=kicker>" + (chosen ? "Your team" : "Showing the home team") +
      "</span><h2>" + esc(t.name) + '</h2><p class="meta">' + t.w + "-" + t.l + "-" + t.otl + " · " + t.pts + " pts · " +
      ord(t.div_rank) + " in the " + esc(t.division) + " · Last 10: " + esc(t.l10) + " · Streak " + esc(t.streak) + "</p></div>" +
      '<button type="button" class="btn ghost" data-open-picker>' + (chosen ? "Change team" : "Pick your team") + "</button></div>";

    if (mine.length) {
      var g = mine[0], R = result(g, team);
      var feat = vids.filter(function (v) { return v.kind === "game" && v.teams.indexOf(R.opp) >= 0; })[0];
      h += '<div class="mt-feature">' + (feat ? ytCard(feat, "big") :
        (g.recap ? '<a class="yt big nhl" href="' + esc(g.recap) + '" target="_blank" rel="noopener"><img src="/img/olympic-hockey-2002-sm.jpg" alt="" loading="lazy"><span class="play"></span><span class="yt-note">Watch the recap on NHL.com</span></a>' : "")) +
        '<div class="mt-last"><span class="kicker">Last game · ' + day(g.date) + '</span><p class="score"><b class="r-' + R.r + '">' +
        R.r + " " + R.a + "-" + R.b + (g.ending !== "REG" ? " (" + g.ending + ")" : "") + "</b> " + (R.us ? "at " : "vs ") +
        esc(name(R.opp)) + '</p><div class="vids">' +
        (g.recap ? '<a class="vid" target="_blank" rel="noopener" href="' + esc(g.recap) + '">&#9654; Recap</a>' : "") +
        (g.condensed ? '<a class="vid" target="_blank" rel="noopener" href="' + esc(g.condensed) + '">&#9654; Condensed game</a>' : "") + "</div>";
      var goals = g.goals.filter(function (x) { return x.team === team && x.clip; });
      if (goals.length) {
        h += '<span class="kicker">Every ' + esc(t.common || "team") + " goal</span><ul class=goals>" + goals.map(function (x) {
          return '<li><a target="_blank" rel="noopener" href="' + esc(x.clip) + '">&#9654; ' + esc(x.scorer) + "</a>" +
            '<span class="meta"> ' + esc(x.time) + (x.strength === "pp" ? " · PP" : x.strength === "sh" ? " · SH" : "") + "</span></li>";
        }).join("") + "</ul>";
      }
      h += "</div></div>";
    }

    var more = vids.filter(function (v) { return !feat || v.id !== feat.id; }).slice(0, 6);
    if (more.length) {
      h += '<h3 class="mt-h">' + esc(t.common || t.name) + ' videos</h3><div class="vgrid">' + more.map(function (v) {
        return '<div class="vcard">' + ytCard(v) + "<p>" + esc(v.title) + '</p><span class="meta">' + views(v.views) + "</span></div>";
      }).join("") + "</div>";
    }

    h += '<div class="mt-cols">';
    if (mine.length > 1) {
      h += '<div class="mt-list"><span class="kicker">Recent results</span><ul>' + mine.slice(1, 6).map(function (g) {
        var R = result(g, team);
        return "<li>" + day(g.date) + ' <b class="r-' + R.r + '">' + R.r + " " + R.a + "-" + R.b + "</b> " + (R.us ? "at " : "vs ") +
          esc(name(R.opp)) + (g.recap ? ' <a target="_blank" rel="noopener" href="' + esc(g.recap) + '">recap</a>' : "") + "</li>";
      }).join("") + "</ul></div>";
    }
    if (next.length) {
      h += '<div class="mt-list"><span class="kicker">Coming up</span><ul>' + next.map(function (g) {
        return "<li>" + when(g) + " · " + (g.away === team ? "at " + esc(name(g.home)) : "vs " + esc(name(g.away))) + "</li>";
      }).join("") + "</ul></div>";
    }
    var div = Object.keys(L.teams).filter(function (ab) { return L.teams[ab].division === t.division; })
      .sort(function (a, b) { return L.teams[a].div_rank - L.teams[b].div_rank; });
    h += '<div class="mt-list"><span class="kicker">' + esc(t.division) + ' Division</span><table class="mini"><tr><th></th><th>Team</th><th>GP</th><th>Pts</th></tr>' +
      div.map(function (ab) {
        var x = L.teams[ab];
        return "<tr" + (ab === team ? ' class="us"' : "") + "><td>" + x.div_rank + "</td><td>" + badge(ab) + " " + esc(x.common || x.name) +
          "</td><td>" + x.gp + "</td><td>" + x.pts + "</td></tr>";
      }).join("") + "</table></div></div>";

    h += '<p class="mt-foot"><a href="/highlights/">Every game this week &rarr;</a>' +
      (team === "UTA" ? ' · <a href="/mammoth/">Mammoth schedule &amp; weekly reports</a>' : "") + "</p>";
    el.innerHTML = h;
  }

  /* ---------- side: most viewed + scores ---------- */
  function renderSide() {
    var el = document.getElementById("mostviewed");
    if (!el || !L) return;
    var cutoff = new Date(Date.now() - 3 * 864e5).toISOString();
    var top = V.filter(function (v) { return v.channel === "NHL" && v.published >= cutoff && v.teams.indexOf(team) < 0; })
      .sort(function (a, b) { return b.views - a.views; }).slice(0, 5);
    if (top.length) {
      el.innerHTML = '<section class="side-box"><span class="kicker">Most viewed around the NHL</span>' + top.map(function (v) {
        return '<div class="side-vid">' + ytCard(v, "sm") + "<div><p>" + esc(v.title) + '</p><span class="meta">' + views(v.views) + "</span></div></div>";
      }).join("") + "</section>";
    } else {
      var big = L.finals.filter(function (g) { return g.away !== team && g.home !== team; }).slice(0, 30)
        .map(function (g) { return {g: g, s: g.as + g.hs + (g.ending !== "REG" ? 3 : 0) - Math.abs(g.as - g.hs)}; })
        .sort(function (a, b) { return b.s - a.s; }).slice(0, 4);
      el.innerHTML = big.length ? '<section class="side-box"><span class="kicker">Games worth watching</span>' + big.map(function (x) {
        var g = x.g;
        return '<div class="side-game">' + badge(g.away) + " " + g.as + ' <span class="at">@</span> ' + badge(g.home) + " " + g.hs +
          (g.ending !== "REG" ? " <span class=ot>" + g.ending + "</span>" : "") + '<br><span class="meta">' + day(g.date) + "</span> " +
          (g.recap ? '<a target="_blank" rel="noopener" href="' + esc(g.recap) + '">&#9654; Recap</a>' : "") + "</div>";
      }).join("") + "</section>" : "";
    }
    document.querySelectorAll(".mini-scores li").forEach(function (li) {
      li.classList.toggle("is-mine", li.getAttribute("data-teams").split(" ").indexOf(team) >= 0);
    });
  }

  /* ---------- highlights page ---------- */
  function filterHighlights() {
    var box = document.getElementById("onlymine");
    if (!box) return;
    document.querySelectorAll(".game").forEach(function (g) {
      var on = g.getAttribute("data-teams").split(" ").indexOf(team) >= 0;
      g.classList.toggle("is-mine", on);
      g.hidden = box.checked && !on;
      if (on) g.parentNode.prepend(g);
    });
  }

  /* ---------- YouTube facade: load the player only on click ---------- */
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("button.yt[data-yt]");
    if (!b) return;
    var f = document.createElement("iframe");
    f.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(b.getAttribute("data-yt")) + "?autoplay=1&rel=0";
    f.title = b.getAttribute("aria-label") || "Video";
    f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
    f.allowFullscreen = true;
    f.className = "yt-frame " + b.className.replace("yt", "");
    b.replaceWith(f);
  });

  function apply() {
    paint();
    document.querySelectorAll("[data-myteam-label]").forEach(function (e) { e.textContent = team; });
    document.querySelectorAll("[data-myteam-name]").forEach(function (e) { e.textContent = name(team); });
    if (dlg) dlg.querySelectorAll("button[data-team]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-team") === team); });
    renderHero(); renderZone(); renderSide(); filterHighlights();
    document.querySelectorAll("[data-open-picker]").forEach(function (b) { b.onclick = open; });
  }

  function open() { if (dlg && dlg.showModal) dlg.showModal(); }
  if (dlg) dlg.querySelectorAll("button[data-team]").forEach(function (b) {
    b.onclick = function () {
      team = b.getAttribute("data-team"); chosen = true;
      try { localStorage.setItem(KEY, team); } catch (e) {}
      dlg.close(); apply(); window.scrollTo({top: 0, behavior: "smooth"});
    };
  });
  var box = document.getElementById("onlymine");
  if (box) box.onchange = filterHighlights;

  apply();
  Promise.all([
    fetch("/data/league.json").then(function (r) { return r.json(); }),
    fetch("/data/videos.json").then(function (r) { return r.ok ? r.json() : {videos: []}; }).catch(function () { return {videos: []}; })
  ]).then(function (res) { L = res[0]; V = res[1].videos || []; apply(); }).catch(function () {});
})();
