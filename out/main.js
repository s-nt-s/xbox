const isLocal = ["", "localhost"].includes(document.location.hostname);
const $$ = (slc) => Array.from(document.querySelectorAll(slc));

class FormQuery {
  static form() {
    const d = {
      tags: [],
      range: {},
    };
    const minmax = /_(max|min)$/;
    document.querySelectorAll("input[id], select[id]").forEach((n) => {
      if (minmax.test(n.id)) return;
      const v = getVal(n.id);
      if (v === false || v === 0) return;
      if (v === true) {
        d.tags.push(n.id);
        return;
      }
      d[n.id] = v;
    });
    d.range = getRanges(
      ...new Set(
        $$("input[id$=_max],input[id$=_min]").map((n) =>
          n.id.replace(minmax, "")
        )
      )
    );
    return d;
  }
  static __form_to_query() {
    if (document.querySelectorAll('.game[style="display: none;"]').length==0) {
      return "all";
    }
    const qr = [];
    const form = FormQuery.form();
    Object.entries(form).forEach(([k, v]) => {
      if (["mode", "range", "tags"].includes(k)) return;
      if (typeof v == "string") v = encodeURIComponent(v);
      qr.push(k + "=" + v);
    });
    Object.entries(form.range).forEach(([k, v]) => {
      qr.push(k + "=" + v.min + "-" + v.max);
    });
    if (form.tags.length)
      qr.push(
        form.mode + "=" + form.tags.map((t) => encodeURIComponent(t)).join("+")
      );
    return qr.join("&");
  }
  static form_to_query() {
    const query = '?' + FormQuery.__form_to_query();
    if (document.location.search == query) return;
    const url = document.location.href.replace(/\?.*$/, "");
    history.pushState({}, "", url + query);
  }
  static query_to_form() {
    const query = FormQuery.query();
    if (query == null) return;
    if (query == "all") {
      setVal("list", "A");
      setVal("mode", "HO");
      setVal("discount", "0");
      setVal("antiquity", $$("#antiquity option").pop().value);
      $$('.chkhideshow input[type="checkbox"]').forEach((i) => setVal(i.id, false));
      $$("input[id$=_min]").forEach((n) => setVal(n.id, n.getAttribute("min")));
      $$("input[id$=_max]").forEach((n) => setVal(n.id, n.getAttribute("max")));
      return;
    }
    Object.entries(query).forEach(([k, v]) => {
      if (["range", "tags"].includes(k)) return;
      setVal(k, v);
    });
    if (query.range)
      Object.entries(query.range).forEach(([k, v]) => {
        setVal(k + "_min", v["min"]);
        setVal(k + "_max", v["max"]);
      });
    if (query.tags)
      document
        .querySelectorAll('.chkhideshow input[type="checkbox"]')
        .forEach((i) => {
          setVal(i.id, query.tags.includes(i.id));
        });
  }
  static query() {
    const mode = Array.from(document.getElementById("mode").options).map(
      (o) => o.value
    );
    const search = document.location.search.replace(/^\?/, "");
    if (search.length == 0) return null;
    if (search == "all") return search;
    const d = {
      tags: [],
      range: {},
    };
    search.split("&").forEach((i) => {
      const [k, v] = FormQuery.__get_kv(i);
      if (k == null) return;
      if (typeof v == "object") {
        d.range[k] = v;
        return;
      }
      if (mode.includes(k)) {
        d["mode"] = k;
        d.tags = v.split("+").map((t) => decodeURIComponent(t));
        return;
      }
      d[k] = v;
    });
    return d;
  }
  static __get_kv(v) {
    const tmp = v.split("=").flatMap((i) => {
      i = i.trim();
      return i.length == 0 ? [] : i;
    });
    if (tmp.length > 2 || tmp[0] == 0) return [null, null];
    const k = tmp[0];
    if (!isNaN(Number(k))) return [null, null];
    if (tmp.length == 2) {
      const v = tmp[1];
      const n = Number(v);
      if (!isNaN(n)) return [k, n];
      if (v.match(/^\d+-\d+$/)) {
        const [_min, _max] = v
          .split("-")
          .map((i) => Number(i))
          .sort((a, b) => a - b);
        return [k, { min: _min, max: _max }];
      }
      return [k, v];
    }
    const opt = document.querySelectorAll(
      'select[id] option[value="' + k + '"]'
    );
    if (opt.length == 1) {
      return [opt[0].closest("select[id]").id, k];
    }
    return [k, true];
  }
}

function mkTag(s) {
  const div = document.createElement("div");
  div.innerHTML = s;
  return div.children[0];
}

function getVal(id) {
  const elm = document.getElementById(id);
  if (elm == null) {
    console.log("No se ha encontrado #" + id);
    return null;
  }
  if (elm.tagName == "INPUT" && elm.getAttribute("type") == "checkbox")
    return elm.checked;
  const val = (elm.value ?? "").trim();
  if (val.length == 0) return null;
  const tp = elm.getAttribute("data-type") || elm.getAttribute("type");
  if (tp == "number") {
    const num = Number(val);
    if (isNaN(num)) return null;
    return num;
  }
  return val;
}

function setVal(id, v) {
  const elm = document.getElementById(id);
  if (elm == null) {
    console.log("No se ha encontrado #" + id);
    return null;
  }
  if (elm.tagName == "INPUT" && elm.getAttribute("type") == "checkbox") {
    elm.checked = v === true;
    return;
  }
  elm.value = v;
}

function filter(slc, fnc) {
  const ok = [];
  const ko = [];
  document.querySelectorAll(slc).forEach((i) => {
    (fnc(i) ? ok : ko).push(i);
  });
  return {
    ok,
    ko,
  };
}

function getRanges() {
  const rgs = {};
  Array.from(arguments).forEach((k) => {
    let mn = getVal(k + "_min");
    let mx = getVal(k + "_max");
    if (mn == null || mx == null) return;
    rgs[k] = { min: mn, max: mx };
  });
  return rgs;
}

function filtrar() {
  const form = FormQuery.form();
  const { ok, ko } = filter("div.game", (i) => {
    const j = GAME[i.id];
    if (j == null) {
      console.log(i.id, "no encontrado", i);
      return true;
    }
    if (form.list == "G" && !j.gamepass) return false;
    if (form.list == "F" && !j.tags.includes("Free")) return false;
    if (form.list == "T" && !j.trial) return false;
    if (j.antiquity != null && j.antiquity > (form.antiquity ?? j.antiquity))
      return false;
    if (j.discount != null && j.discount < (form.discount ?? 0)) return false;

    const fl = (() => {
      if (form.tags.length == 0) {
        if (form.mode[0] == "S") return false;
        if (form.mode[0] == "H") return true;
      }
      const hs = form.tags.filter((v) => j.tags.includes(v));
      if (form.mode == "SO") return hs.length > 0;
      if (form.mode == "HO") return hs.length == 0;
      if (form.mode == "SA") return hs.length == form.tags.length;
      if (form.mode == "HA") return hs.length != form.tags.length;
      console.log(form.mode, form.tags, j.tags, hs);
    })();
    if (!fl) return false;

    const ok_rgs = Object.entries(form.range).map(([k, value]) => {
      const vl = j[k];
      if (vl == null) {
        console.log(i.id, "no tine", k);
        return true;
      }
      return vl >= value["min"] && vl <= value["max"];
    });
    if (ok_rgs.includes(false)) return false;

    return true;
  });
  ok.forEach((i) => (i.style.display = ""));
  ko.forEach((i) => (i.style.display = "none"));
  if (ko.length == 0) {
    document.title = `${ok.length} juegos`;
  } else {
    document.title = `${ok.length}/${ok.length + ko.length} juegos`;
  }
  document.getElementById("games").classList.remove("hideIfJS");
  FormQuery.form_to_query();
}

function fixAntiguedad() {
  const opts = document.getElementById("antiquity").options;
  const head = opts.length - 1;
  const done = [];
  const days_to_lab = (ant) => {
    if (ant < 30) return { txt: "día", num: ant };
    if (ant < 365) return { txt: "mes", num: Math.ceil(ant / 30), s: "es" };
    return { txt: "año", num: Math.ceil(ant / 365) };
  };
  Array.from(opts)
    .reverse()
    .forEach((o, i) => {
      const ant = Number(o.value) + ANTIQUITY;
      const lab = days_to_lab(ant);
      if (done.includes(lab.txt + lab.num)) {
        o.remove();
        return;
      } /*
    if (i>0 && i<head && (lab.num>1 && (lab.num%2)==1)) {
      o.remove();
      return;
    }*/
      done.push(lab.txt + lab.num);
      if (lab.txt != "día" || ANTIQUITY > 0) {
        o.textContent =
          lab.num + " " + lab.txt + (lab.num != 1 ? lab.s ?? "s" : "");
      }
    });
}

function ifLocal() {
  if (!isLocal) return;
  document.querySelectorAll("div.game[id]:not([id='']) > p").forEach((p) => {
    p.appendChild(document.createElement("br"));
    ["ac", "gm", "ps", "rw"].forEach((path, i) => {
      if (i > 0) p.appendChild(document.createTextNode(" - "));
      p.appendChild(
        mkTag(`
      <a href="../rec/${path}/${p.parentNode.id}.json">${path}</a>
    `)
      );
    });
  });
}

function fixImg() {
  document.getElementsByTagName("img").forEach((i) => {
    i.addEventListener("error", function () {
      const n = Number(this.getAttribute("data-retry"));
      if (n > 3) return;
      setTimeout(() => {
        this.src = this.src;
        this.setAttribute("data-retry", n + 1);
      }, 3000);
    });
  });
}

document.addEventListener(
  "DOMContentLoaded",
  () => {
    ifLocal();
    fixAntiguedad();
    FormQuery.query_to_form();
    document.querySelectorAll("input, select").forEach((i) => {
      i.addEventListener("change", filtrar);
    });
    filtrar();
  },
  false
);
