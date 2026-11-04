/* Hockey Network USA: "choose your team".
   The choice lives only in this browser (localStorage). With no choice the
   site shows the Utah Mammoth. Every team always gets its own colors (set
   before paint by the inline script in <head>), and the home page is built
   around that team: hero photo, next game and odds, last game and goals,
   team news, leaders, schedule and standings. The side column keeps the rest
   of the league: tonight's games, most viewed videos, scores, league news
   and league leaders. Videos play in YouTube's privacy-enhanced player. */
(function () {
  var KEY = "hnusa-team", DEFAULT = "UTA", team = DEFAULT, chosen = false;
  var L = null, V = [], S = null, N = null;
  try { var saved = localStorage.getItem(KEY); if (saved) { team = saved; chosen = true; } } catch (e) {}
  var dlg = document.getElementById("teampick");
  var THEMES = window.HNUSA_THEMES || {}, PH = window.HNUSA_PHOTOS || {teams: {}, action: []};
  var standView = "division";

  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"}[c]; }); }
  function badge(ab, cls) {
    var b = dlg && dlg.querySelector('button[data-team="' + ab + '"] .badge');
    var h = b ? b.outerHTML : '<span class="badge">' + esc(ab) + "</span>";
    return cls ? h.replace('class="badge"', 'class="badge ' + cls + '"') : h;
  }
  function T(ab) { return (L && L.teams[ab]) || null; }
  function name(ab) { var t = T(ab); return t ? t.name : ab; }
  function short(ab) { var t = T(ab); return t ? (t.common || t.name) : ab; }
  function ord(n) { n = +n; var s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }
  function day(iso) { return new Date(iso + "T12:00:00").toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"}); }
  function time(iso) { return new Date(iso).toLocaleTimeString(undefined, {hour: "numeric", minute: "2-digit", timeZoneName: "short"}); }
  function when(g) { return g.start ? new Date(g.start).toLocaleDateString(undefined, {weekday: "short", month: "short", day: "numeric"}) + " · " + time(g.start) : day(g.date); }
  function ago(iso) {
    var h = (Date.now() - new Date(iso)) / 36e5;
    return h < 1 ? "just now" : h < 24 ? Math.round(h) + "h ago" : Math.round(h / 24) + "d ago";
  }
  function views(n) { return n >= 1e6 ? (n / 1e6).toFixed(1) + "M views" : n >= 1e3 ? Math.round(n / 1e3) + "K views" : n + " views"; }
  function result(g, ab) {
    var us = g.away === ab, a = us ? g.as : g.hs, b = us ? g.hs : g.as;
    return {us: us, a: a, b: b, r: a > b ? "W" : (g.ending === "OT" || g.ending === "SO") ? "OTL" : "L", opp: us ? g.home : g.away};
  }
  function ytCard(v, cls) {
    return '<button type="button" class="yt ' + (cls || "") + '" data-yt="' + esc(v.id) + '" aria-label="Play ' + esc(v.title) + '">' +
      '<img src="' + esc(v.thumb) + '" alt="" loading="lazy"><span class="play"></span></button>';
  }
  function teamVideos(ab) { return V.filter(function (v) { return v.teams && v.teams.indexOf(ab) >= 0; }); }
  function mineGames(list) { return list.filter(function (g) { return g.away === team || g.home === team; }); }
  function photoFor(ab) {
    if (PH.teams[ab]) return PH.teams[ab];
    var a = PH.action || [];
    if (!a.length) return null;
    var h = 0; for (var i = 0; i < ab.length; i++) h += ab.charCodeAt(i);
    return a[h % a.length];
  }
  function odds(g) {
    if (!g.odds) return "";
    return '<span class="odds" title="Moneyline from ' + esc(g.odds.book) + '">' + badge(g.away, "xs") + " " + esc(g.odds.away) +
      " · " + badge(g.home, "xs") + " " + esc(g.odds.home) + "</span>";
  }
  function panel(title, body, cls) {
    return '<section class="panel ' + (cls || "") + '"><h2 class="ph">' + title + "</h2>" + body + "</section>";
  }

  /* ---------- theme ---------- */
  function paint() {
    var r = document.documentElement, c = THEMES[team];
    if (c && chosen) { r.dataset.team = team; for (var k in c) r.style.setProperty("--" + k, c[k]); }
    else if (THEMES[DEFAULT]) { delete r.dataset.team; for (var k2 in THEMES[DEFAULT]) r.style.removeProperty("--" + k2); }
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute("content", (c && chosen ? c : THEMES[DEFAULT] || {tc1: "#010101"}).tc1);
  }

  /* ---------- hero ---------- */
  function renderHero() {
    var el = document.getElementById("thero");
    if (!el) return;
    var p = photoFor(team);
    if (p) { el.style.setProperty("--hero-img", "url(" + p.src + ")"); el.classList.add("has-photo"); }
    var cr = el.querySelector(".credit"); if (cr && p) cr.textContent = "Photo: " + p.credit;
    var t = T(team), box = el.querySelector(".th-main");
    if (!t || !box) return;
    var gd = t.gf - t.ga;
    box.innerHTML = '<p class="kicker">' + (chosen ? "Your team" : "Utah's team") + " · " + esc(t.division) + " Division</p>" +
      "<h1>" + esc(t.name) + "</h1>" +
      '<div class="chips">' +
      "<span><b>" + t.w + "-" + t.l + "-" + t.otl + "</b>Record</span>" +
      "<span><b>" + t.pts + "</b>Points</span>" +
      "<span><b>" + ord(t.div_rank) + "</b>" + esc(t.division) + "</span>" +
      "<span><b>" + ord(t.league_rank) + "</b>NHL</span>" +
      "<span><b>" + esc(t.l10) + "</b>Last 10</span>" +
      "<span><b>" + esc(t.streak) + "</b>Streak</span>" +
      (t.gf != null ? "<span><b>" + (gd > 0 ? "+" : "") + gd + "</b>Goal diff</span>" : "") +
      "</div>" +
      '<button type="button" class="btn alt" data-open-picker>' + (chosen ? "Change team" : "Pick your team") + "</button>";
    var n = mineGames(L.upcoming)[0], nx = el.querySelector(".th-next");
    if (nx) nx.innerHTML = n ? '<div class="nextgame"><span class="kicker">Next game</span><div class="ng-teams">' + badge(n.away, "big") +
      '<span class="at">@</span>' + badge(n.home, "big") + "</div><strong>" + (n.away === team ? "at " + esc(name(n.home)) : "vs " + esc(name(n.away))) +
      "</strong><span>" + when(n) + (n.venue ? " · " + esc(n.venue) : "") + "</span>" +
      (n.odds ? '<div class="ng-odds"><span class="kicker">Odds · ' + esc(n.odds.book) + "</span>" + odds(n) + "</div>" : "") +
      "</div>" : "";
  }

  /* ---------- team zone ---------- */
  function lastGame(t) {
    var mine = mineGames(L.finals);
    if (!mine.length) return "";
    var g = mine[0], R = result(g, team), vids = teamVideos(team);
    var feat = vids.filter(function (v) { return v.kind === "game" && v.teams.indexOf(R.opp) >= 0; })[0];
    var p = photoFor(team);
    var media = feat ? ytCard(feat, "big") : g.recap ? '<a class="yt big nhl" href="' + esc(g.recap) + '" target="_blank" rel="noopener">' +
      (p ? '<img src="' + esc(p.sm) + '" alt="" loading="lazy">' : "") + '<span class="play"></span><span class="yt-note">Watch the recap on NHL.com</span></a>' : "";
    var goals = g.goals.filter(function (x) { return x.team === team; });
    return panel("Last game · " + day(g.date),
      '<div class="lg">' + media + '<div class="lg-info"><div class="lg-score r-' + R.r + '">' +
      '<div>' + badge(g.away, "big") + "<b>" + g.as + "</b></div><div>" + badge(g.home, "big") + "<b>" + g.hs + "</b></div>" +
      '<span class="lg-res">' + (R.r === "W" ? "Win" : R.r === "OTL" ? g.ending + " loss" : "Loss") + (g.ending !== "REG" && R.r === "W" ? " in " + g.ending : "") + "</span></div>" +
      '<div class="vids">' + (g.recap ? '<a class="vid" target="_blank" rel="noopener" href="' + esc(g.recap) + '">&#9654; Recap</a>' : "") +
      (g.condensed ? '<a class="vid" target="_blank" rel="noopener" href="' + esc(g.condensed) + '">&#9654; Condensed game</a>' : "") + "</div>" +
      (goals.length ? '<span class="kicker">' + esc(short(team)) + " goals</span><ul class=goals>" + goals.map(function (x) {
        return "<li>" + (x.clip ? '<a target="_blank" rel="noopener" href="' + esc(x.clip) + '">&#9654; ' + esc(x.scorer) + "</a>" : esc(x.scorer)) +
          '<span class="meta"> ' + esc(x.time) + (x.strength === "pp" ? " · PP" : x.strength === "sh" ? " · SH" : "") + "</span></li>";
      }).join("") + "</ul>" : "") + "</div></div>", "wide");
  }

  function newsPanel(t, all) {
    var items = N && N.teams && N.teams[team];
    if (!items || !items.length) return "";
    var p = photoFor(team);
    return panel(esc(short(team)) + " news", '<ul class="newslist">' + items.slice(0, all ? 20 : 7).map(function (x, i) {
      return '<li' + (i === 0 ? ' class="lead"' : "") + '><a href="' + esc(x.link) + '" target="_blank" rel="noopener">' +
        (i === 0 && p ? '<img src="' + esc(p.sm) + '" alt="" loading="lazy">' : "") +
        "<b>" + esc(x.title) + '</b><span class="meta">' + esc(x.source) + (x.date ? " · " + ago(x.date) : "") + "</span></a></li>";
    }).join("") + '</ul><p class="meta small">Headlines link to the original stories.</p>', "wide news-panel");
  }

  function schedulePanel() {
    var mine = mineGames(L.finals).slice(0, 5), next = mineGames(L.upcoming).slice(0, 5);
    if (!mine.length && !next.length) return "";
    var h = '<div class="two">';
    h += '<div><span class="kicker">Coming up</span><ul class="sched-list">' + (next.length ? next.map(function (g) {
      return "<li><span>" + when(g) + "</span><b>" + (g.away === team ? "at " : "vs ") + badge(g.away === team ? g.home : g.away, "xs") + " " +
        esc(short(g.away === team ? g.home : g.away)) + "</b>" + odds(g) + "</li>";
    }).join("") : "<li>No games this week</li>") + "</ul>" +
      (next.some(function (g) { return g.odds; }) ? '<p class="meta small">Moneyline odds for information only, from ' + esc((next.filter(function (g) { return g.odds; })[0].odds || {}).book) +
        ". Sports betting isn't legal in Utah. 21+ where it is.</p>" : "") + "</div>";
    h += '<div><span class="kicker">Recent results</span><ul class="sched-list">' + mine.map(function (g) {
      var R = result(g, team);
      return "<li><span>" + day(g.date) + '</span><b><i class="r-' + R.r + '">' + R.r + "</i> " + R.a + "-" + R.b + (g.ending !== "REG" ? " " + g.ending : "") +
        " " + (R.us ? "at " : "vs ") + esc(short(R.opp)) + "</b>" + (g.recap ? '<a target="_blank" rel="noopener" href="' + esc(g.recap) + '">recap</a>' : "") + "</li>";
    }).join("") + "</ul></div></div>";
    return panel("Schedule", h);
  }

  function leadersPanel() {
    var st = S && S.teams && S.teams[team];
    if (!st || !st.skaters || !st.skaters.length) return "";
    var top = st.skaters[0];
    var h = '<div class="leader-top"><span class="kicker">Points leader</span><b>' + esc(top.name) + "</b><span>" + top.g + " G · " + top.a + " A · " +
      top.p + " PTS</span></div>";
    h += '<table class="mini"><tr><th>Player</th><th>GP</th><th>G</th><th>A</th><th>P</th><th>+/-</th></tr>' + st.skaters.map(function (p) {
      return "<tr><td>" + esc(p.name) + ' <span class="meta">' + esc(p.pos) + "</span></td><td>" + p.gp + "</td><td>" + p.g + "</td><td>" + p.a +
        "</td><td><b>" + p.p + "</b></td><td>" + (p.pm > 0 ? "+" : "") + p.pm + "</td></tr>";
    }).join("") + "</table>";
    if (st.goalies && st.goalies.length) {
      h += '<table class="mini"><tr><th>Goalie</th><th>GP</th><th>W-L-OT</th><th>SV%</th><th>GAA</th></tr>' + st.goalies.map(function (p) {
        return "<tr><td>" + esc(p.name) + "</td><td>" + p.gp + "</td><td>" + p.w + "-" + p.l + "-" + p.otl + "</td><td>" + p.svp.toFixed(3).replace(/^0/, "") +
          "</td><td>" + p.gaa.toFixed(2) + "</td></tr>";
      }).join("") + "</table>";
    }
    return panel(esc(short(team)) + " stat leaders", h);
  }

  function standingsPanel(t) {
    var all = Object.keys(L.teams), list, label;
    if (standView === "division") { list = all.filter(function (ab) { return L.teams[ab].division === t.division; }); label = "div_rank"; }
    else if (standView === "conference") { list = all.filter(function (ab) { return L.teams[ab].conference === t.conference; }); label = "conf_rank"; }
    else { list = all; label = "league_rank"; }
    list.sort(function (a, b) { return L.teams[a][label] - L.teams[b][label]; });
    var tabs = '<div class="tabs" role="tablist">' + [["division", t.division], ["conference", t.conference], ["league", "NHL"]].map(function (x) {
      return '<button type="button" role="tab" data-stand="' + x[0] + '" aria-selected="' + (standView === x[0]) + '">' + esc(x[1]) + "</button>";
    }).join("") + "</div>";
    var rows = list.map(function (ab) {
      var x = L.teams[ab], gd = x.gf - x.ga;
      return "<tr" + (ab === team ? ' class="us"' : "") + "><td>" + x[label] + "</td><td>" + badge(ab, "xs") + " " + esc(x.common || x.name) + "</td><td>" + x.gp +
        "</td><td>" + x.w + "-" + x.l + "-" + x.otl + "</td><td><b>" + x.pts + '</b></td><td class="hide-s">' + (x.gf != null ? (gd > 0 ? "+" : "") + gd : "") +
        '</td><td class="hide-s">' + esc(x.l10) + '</td><td class="hide-s">' + esc(x.streak) + "</td></tr>";
    }).join("");
    return panel("Standings", tabs + '<div class="tscroll"><table class="mini stand"><tr><th></th><th>Team</th><th>GP</th><th>Record</th><th>Pts</th>' +
      '<th class="hide-s">Diff</th><th class="hide-s">L10</th><th class="hide-s">Strk</th></tr>' + rows + "</table></div>", "standings");
  }

  function videosPanel() {
    var vids = teamVideos(team).slice(0, 6);
    if (!vids.length) return "";
    return panel(esc(short(team)) + " videos", '<div class="vgrid">' + vids.map(function (v) {
      return '<div class="vcard">' + ytCard(v) + "<p>" + esc(v.title) + '</p><span class="meta">' + views(v.views) + "</span></div>";
    }).join("") + "</div>", "wide");
  }

  function renderZone() {
    var el = document.getElementById("myteam");
    if (!el || !L) return;
    var t = T(team);
    if (!t) { el.innerHTML = ""; return; }
    el.innerHTML = lastGame(t) + newsPanel(t) + schedulePanel() + leadersPanel() + videosPanel() + standingsPanel(t) +
      '<p class="mt-foot"><a href="/highlights/">Every game this week, with highlights &rarr;</a>' +
      (team === "UTA" ? ' · <a href="/mammoth/">Mammoth schedule &amp; weekly reports &rarr;</a>' : "") + "</p>";
  }

  /* ---------- team pages: /news/, /stats/, /standings/ ---------- */
  function renderPages() {
    var t = T(team);
    var ph = document.querySelector(".pagehead[data-teamphoto]"), p = photoFor(team);
    if (ph && p) { ph.style.setProperty("--hero-img", "url(" + p.src + ")"); ph.classList.add("has-photo");
      var cr = ph.querySelector(".credit"); if (cr) cr.textContent = "Photo: " + p.credit; }
    if (!t) return;
    var el = document.getElementById("newspage");
    if (el) {
      var items = (N && N.teams && N.teams[team]) || [], lg = (N && N.league) || [];
      el.innerHTML = (items.length ? newsPanel(t, true) : "") +
        (lg.length ? panel("Around the NHL", '<ul class="newslist">' + lg.map(function (x) {
          return '<li><a href="' + esc(x.link) + '" target="_blank" rel="noopener"><b>' + esc(x.title) + '</b><span class="meta">' + esc(x.source) +
            (x.date ? " · " + ago(x.date) : "") + "</span></a></li>";
        }).join("") + "</ul>", "wide") : "");
    }
    el = document.getElementById("statspage");
    if (el) {
      var lead = S && S.leaders && S.leaders.points ? panel("NHL leaders", [["points", "Points"], ["goals", "Goals"], ["assists", "Assists"]].map(function (c) {
        return '<span class="kicker">' + c[1] + '</span><ol class="leaders">' + (S.leaders[c[0]] || []).map(function (q) {
          return "<li" + (q.team === team ? ' class="is-mine"' : "") + ">" + badge(q.team, "xs") + " <span>" + esc(q.name) + "</span><b>" + q.value + "</b></li>";
        }).join("") + "</ol>";
      }).join("")) : "";
      el.innerHTML = leadersPanel() + lead + schedulePanel();
    }
    el = document.getElementById("standpage");
    if (el) el.innerHTML = standingsPanel(t);
  }

  /* ---------- side column: the rest of the league ---------- */
  function renderSide() {
    if (!L) return;
    var el = document.getElementById("tonight");
    if (el) {
      var first = L.upcoming[0], dd = first && first.date;
      var games = L.upcoming.filter(function (g) { return g.date === dd; }).slice(0, 10);
      el.innerHTML = games.length ? '<section class="side-box"><h3 class="sh">Games · ' + day(dd) + '</h3><ul class="tonight">' + games.map(function (g) {
        return '<li data-teams="' + g.away + " " + g.home + '"><div>' + badge(g.away, "xs") + ' <span class="at">@</span> ' + badge(g.home, "xs") +
          ' <span class="meta">' + (g.start ? time(g.start) : "") + "</span></div>" + (g.odds ? '<div class="o">' + esc(g.odds.away) + " / " + esc(g.odds.home) + "</div>" : "") + "</li>";
      }).join("") + "</ul>" + (games.some(function (g) { return g.odds; }) ? '<p class="meta small">Moneyline (away / home). Info only, 21+.</p>' : "") + "</section>" : "";
    }
    el = document.getElementById("mostviewed");
    if (el) {
      var cutoff = new Date(Date.now() - 3 * 864e5).toISOString();
      var top = V.filter(function (v) { return v.channel === "NHL" && v.published >= cutoff && v.teams.indexOf(team) < 0; })
        .sort(function (a, b) { return b.views - a.views; }).slice(0, 5);
      if (top.length) {
        el.innerHTML = '<section class="side-box"><h3 class="sh">Most viewed around the NHL</h3>' + top.map(function (v) {
          return '<div class="side-vid">' + ytCard(v, "sm") + "<div><p>" + esc(v.title) + '</p><span class="meta">' + views(v.views) + "</span></div></div>";
        }).join("") + "</section>";
      } else {
        var big = L.finals.filter(function (g) { return g.away !== team && g.home !== team; }).slice(0, 30)
          .map(function (g) { return {g: g, s: g.as + g.hs + (g.ending !== "REG" ? 3 : 0) - Math.abs(g.as - g.hs)}; })
          .sort(function (a, b) { return b.s - a.s; }).slice(0, 4);
        el.innerHTML = big.length ? '<section class="side-box"><h3 class="sh">Games worth watching</h3>' + big.map(function (x) {
          var g = x.g;
          return '<div class="side-game">' + badge(g.away, "xs") + " " + g.as + ' <span class="at">@</span> ' + badge(g.home, "xs") + " " + g.hs +
            (g.ending !== "REG" ? " <span class=ot>" + g.ending + "</span>" : "") + ' <span class="meta">' + day(g.date) + "</span> " +
            (g.recap ? '<a target="_blank" rel="noopener" href="' + esc(g.recap) + '">&#9654; Recap</a>' : "") + "</div>";
        }).join("") + "</section>" : "";
      }
    }
    el = document.getElementById("leaguenews");
    if (el && N && N.league && N.league.length) {
      el.innerHTML = '<section class="side-box"><h3 class="sh">NHL news</h3><ul class="side-news">' + N.league.slice(0, 6).map(function (x) {
        return '<li><a href="' + esc(x.link) + '" target="_blank" rel="noopener">' + esc(x.title) + '</a><span class="meta">' + esc(x.source) +
          (x.date ? " · " + ago(x.date) : "") + "</span></li>";
      }).join("") + "</ul></section>";
    }
    el = document.getElementById("leagueleaders");
    if (el && S && S.leaders && S.leaders.points && S.leaders.points.length) {
      el.innerHTML = '<section class="side-box"><h3 class="sh">NHL leaders</h3>' + [["points", "Points"], ["goals", "Goals"]].map(function (c) {
        return '<span class="kicker">' + c[1] + '</span><ol class="leaders">' + (S.leaders[c[0]] || []).map(function (p) {
          return "<li" + (p.team === team ? ' class="is-mine"' : "") + ">" + badge(p.team, "xs") + " <span>" + esc(p.name) + "</span><b>" + p.value + "</b></li>";
        }).join("") + "</ol>";
      }).join("") + "</section>";
    }
    document.querySelectorAll(".mini-scores li, .tonight li").forEach(function (li) {
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

  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("button.yt[data-yt]");
    if (b) {  /* YouTube facade: load the player only on click */
      var f = document.createElement("iframe");
      f.src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(b.getAttribute("data-yt")) + "?autoplay=1&rel=0";
      f.title = b.getAttribute("aria-label") || "Video";
      f.allow = "autoplay; encrypted-media; picture-in-picture; fullscreen";
      f.allowFullscreen = true;
      f.className = "yt-frame " + b.className.replace("yt", "");
      b.replaceWith(f);
      return;
    }
    var s = e.target.closest && e.target.closest("button[data-stand]");
    if (s) { standView = s.getAttribute("data-stand"); renderZone(); renderPages(); bind(); }
  });

  function bind() { document.querySelectorAll("[data-open-picker]").forEach(function (b) { b.onclick = open; }); }
  function apply() {
    paint();
    document.querySelectorAll("[data-myteam-label]").forEach(function (e) { e.textContent = team; });
    document.querySelectorAll("[data-myteam-name]").forEach(function (e) { e.textContent = name(team); });
    if (dlg) dlg.querySelectorAll("button[data-team]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-team") === team); });
    if (L) { renderHero(); renderZone(); renderSide(); renderPages(); }
    filterHighlights();
    bind();
  }

  function open() { if (dlg && dlg.showModal) dlg.showModal(); }
  if (dlg) dlg.querySelectorAll("button[data-team]").forEach(function (b) {
    b.onclick = function () {
      team = b.getAttribute("data-team"); chosen = true; standView = "division";
      try { localStorage.setItem(KEY, team); } catch (e) {}
      dlg.close(); apply(); window.scrollTo({top: 0, behavior: "smooth"});
    };
  });
  var box = document.getElementById("onlymine");
  if (box) box.onchange = filterHighlights;

  function get(u, empty) { return fetch(u).then(function (r) { return r.ok ? r.json() : empty; }).catch(function () { return empty; }); }
  apply();
  if (document.querySelector("#myteam, #thero, .teampage, [data-myteam-name]")) {
    Promise.all([get("/data/league.json", null), get("/data/videos.json", {videos: []}), get("/data/stats.json", null), get("/data/news.json", null)])
      .then(function (res) { L = res[0]; V = (res[1] || {}).videos || []; S = res[2]; N = res[3]; if (L) apply(); });
  }
})();
